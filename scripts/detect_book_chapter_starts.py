"""Detect each chapter's audio start time inside book/chapter mp4s.

Why: the previous timestamp model assumed a fixed 3s book intro pad and 3s
chapter title pad in audio, but in reality the concatenated book audio has
variable-length silences between chapters (~8s) and a tiny ~1s lead before
the first verse. Computing chapter offsets from local mp4 durations therefore
overshoots real verse positions by ~5 seconds. This script measures the real
audio chapter boundaries directly by finding the silent regions inside each
book mp4's audio sample table.

Output (`temp/book_chapter_starts.csv`):
    book,chapter,start_seconds
    창세기,1,0.998         # per-chapter video; first audio onset
    창세기,2,0.998         # ...
    유다서,1,0.998         # single-chapter book; first audio onset
    시편,1,0.998           # book video first verse
    시편,2,64.359          # book video chapter 2 audio onset
    ...
"""

from __future__ import annotations

import csv
import struct
import sys
from pathlib import Path

TTS_ROOT = Path("temp/tts_result-slow")
OUTPUT_CSV = Path("temp/book_chapter_starts.csv")

# A silent AAC sample is typically 4-15 bytes; a voiced sample is 80-700 bytes.
# Threshold of 20 bytes cleanly separates them.
SILENCE_SAMPLE_SIZE_THRESHOLD = 20

# Inter-chapter silences are normally ~8s. The known anomaly (민수기 ch20 with
# corrupt verses 24-29) drops one boundary to ~5s. Threshold 4s catches both
# without flagging within-chapter pauses (max ~2s between verses).
INTER_CHAPTER_MIN_SILENCE_SEC = 4.0


def _read_atom_header(buf: bytes, offset: int):
    if offset + 8 > len(buf):
        return None
    size = struct.unpack(">I", buf[offset : offset + 4])[0]
    atom_type = buf[offset + 4 : offset + 8].decode("ascii", errors="replace")
    payload = offset + 8
    if size == 1:
        if offset + 16 > len(buf):
            return None
        size = struct.unpack(">Q", buf[offset + 8 : offset + 16])[0]
        payload = offset + 16
    elif size == 0:
        size = len(buf) - offset
    return size, atom_type, payload


def _find_atom(buf: bytes, start: int, end: int, target: str):
    pos = start
    while pos < end:
        h = _read_atom_header(buf, pos)
        if h is None:
            return None
        size, t, payload = h
        if t == target:
            return payload, pos + size
        pos += size
    return None


def _find_all_atoms(buf: bytes, start: int, end: int, target: str):
    out = []
    pos = start
    while pos < end:
        h = _read_atom_header(buf, pos)
        if h is None:
            return out
        size, t, payload = h
        if t == target:
            out.append((payload, pos + size))
        pos += size
    return out


def parse_audio_track(data: bytes):
    """Return (timescale, sample_sizes, sample_durations) for the audio track.

    Raises ValueError if the file has no moov / no audio trak / required atoms missing.
    """
    moov = _find_atom(data, 0, len(data), "moov")
    if not moov:
        raise ValueError("no moov atom")
    moov_p, moov_e = moov

    audio_trak = None
    for tp, te in _find_all_atoms(data, moov_p, moov_e, "trak"):
        mdia = _find_atom(data, tp, te, "mdia")
        if not mdia:
            continue
        mp, me = mdia
        hdlr = _find_atom(data, mp, me, "hdlr")
        if not hdlr:
            continue
        hp, _ = hdlr
        if hp + 16 > len(data):
            continue
        if data[hp + 8 : hp + 12].decode("ascii", errors="replace") == "soun":
            audio_trak = (tp, te)
            break
    if audio_trak is None:
        raise ValueError("no audio trak")

    tp, te = audio_trak
    mp, me = _find_atom(data, tp, te, "mdia")
    mhp, _ = _find_atom(data, mp, me, "mdhd")
    version = data[mhp]
    if version == 1:
        timescale = struct.unpack(">I", data[mhp + 4 + 16 : mhp + 4 + 20])[0]
    else:
        timescale = struct.unpack(">I", data[mhp + 4 + 8 : mhp + 4 + 12])[0]

    minf_p, minf_e = _find_atom(data, mp, me, "minf")
    sp, se = _find_atom(data, minf_p, minf_e, "stbl")

    szp, _ = _find_atom(data, sp, se, "stsz")
    sample_size = struct.unpack(">I", data[szp + 4 : szp + 8])[0]
    sample_count = struct.unpack(">I", data[szp + 8 : szp + 12])[0]
    if sample_size != 0:
        sizes = [sample_size] * sample_count
    else:
        sizes = list(struct.unpack(f">{sample_count}I", data[szp + 12 : szp + 12 + 4 * sample_count]))

    ttsp, _ = _find_atom(data, sp, se, "stts")
    entry_count = struct.unpack(">I", data[ttsp + 4 : ttsp + 8])[0]
    durations: list[int] = []
    for i in range(entry_count):
        cnt = struct.unpack(">I", data[ttsp + 8 + 8 * i : ttsp + 12 + 8 * i])[0]
        dlt = struct.unpack(">I", data[ttsp + 12 + 8 * i : ttsp + 16 + 8 * i])[0]
        durations.extend([dlt] * cnt)

    n = min(len(durations), len(sizes))
    return timescale, sizes[:n], durations[:n]


def first_audio_onset_seconds(data: bytes) -> float:
    """Return the time (seconds) of the first non-silent audio sample."""
    timescale, sizes, durations = parse_audio_track(data)
    t = 0
    for sz, dt in zip(sizes, durations):
        if sz > SILENCE_SAMPLE_SIZE_THRESHOLD:
            return t / timescale
        t += dt
    raise ValueError("no audio onset found (all samples are silent)")


def chapter_audio_starts(data: bytes, chapter_count: int) -> list[float]:
    """Return audio start time (seconds) for each chapter inside a concatenated book mp4.

    Strategy:
      - First chapter starts at the file's first non-silent sample.
      - Each subsequent chapter starts at the END of the inter-chapter silent
        region preceding it. We expect exactly `chapter_count - 1` such regions.
    """
    timescale, sizes, durations = parse_audio_track(data)
    starts: list[float] = []
    t = 0
    run_start_t: int | None = None
    run_end_t = 0
    first_onset_seen = False

    for sz, dt in zip(sizes, durations):
        if sz > SILENCE_SAMPLE_SIZE_THRESHOLD:
            if not first_onset_seen:
                starts.append(t / timescale)
                first_onset_seen = True
            elif run_start_t is not None:
                run_dur = (run_end_t - run_start_t) / timescale
                if run_dur >= INTER_CHAPTER_MIN_SILENCE_SEC:
                    starts.append(t / timescale)
            run_start_t = None
        else:
            if run_start_t is None:
                run_start_t = t
            run_end_t = t + dt
        t += dt

    if len(starts) != chapter_count:
        raise ValueError(
            f"expected {chapter_count} chapter starts, found {len(starts)} "
            f"(silence threshold {INTER_CHAPTER_MIN_SILENCE_SEC}s)"
        )
    return starts


def build_book_short_map(tts_root: Path) -> dict[str, str]:
    if not tts_root.is_dir():
        return {}
    out: dict[str, str] = {}
    for book_dir in tts_root.iterdir():
        if not book_dir.is_dir():
            continue
        for f in book_dir.iterdir():
            if f.is_file() and f.suffix == ".mp4":
                out[f.stem] = book_dir.name
                break
    return out


def collect_chapter_count_per_book(tts_root: Path, book_short: dict[str, str]) -> dict[str, int]:
    """Count `{short}/N/` directories where N is a positive integer."""
    counts: dict[str, int] = {}
    for full, short in book_short.items():
        d = tts_root / short
        n = 0
        if d.is_dir():
            for sub in d.iterdir():
                if sub.is_dir() and sub.name.isdigit() and int(sub.name) > 0:
                    n += 1
        counts[full] = n
    return counts


def collect_rows(tts_root: Path, book_short: dict[str, str], chapter_counts: dict[str, int],
                 genesis_book: str = "창세기") -> tuple[list[tuple[str, int, float]], list[str]]:
    rows: list[tuple[str, int, float]] = []
    warnings: list[str] = []
    for full, short in sorted(book_short.items()):
        if full == genesis_book:
            chapter_dir_root = tts_root / short / "0"
            n = chapter_counts.get(full, 0)
            for c in range(1, n + 1):
                mp4 = chapter_dir_root / f"{full}-{c}장.mp4"
                if not mp4.is_file():
                    warnings.append(f"{full} ch{c}: per-chapter mp4 missing ({mp4})")
                    continue
                try:
                    onset = first_audio_onset_seconds(mp4.read_bytes())
                except Exception as exc:
                    warnings.append(f"{full} ch{c}: parse failed: {exc}")
                    continue
                rows.append((full, c, onset))
        else:
            book_mp4 = tts_root / short / f"{full}.mp4"
            n = chapter_counts.get(full, 0)
            if n == 0:
                continue
            if not book_mp4.is_file():
                warnings.append(f"{full}: book mp4 missing ({book_mp4})")
                continue
            try:
                starts = chapter_audio_starts(book_mp4.read_bytes(), n)
            except Exception as exc:
                warnings.append(f"{full}: detection failed: {exc}")
                continue
            for c, s in enumerate(starts, start=1):
                rows.append((full, c, s))
    return rows, warnings


def write_csv(rows: list[tuple[str, int, float]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["book", "chapter", "start_seconds"])
        for book, ch, sec in rows:
            w.writerow([book, ch, f"{sec:.3f}"])
    tmp.replace(path)


def main() -> None:
    book_short = build_book_short_map(TTS_ROOT)
    counts = collect_chapter_count_per_book(TTS_ROOT, book_short)
    rows, warnings = collect_rows(TTS_ROOT, book_short, counts)
    write_csv(rows, OUTPUT_CSV)
    print(f"books={len(book_short)} rows={len(rows)} warnings={len(warnings)} output={OUTPUT_CSV}",
          file=sys.stderr)
    for w in warnings:
        print(f"  warn: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
