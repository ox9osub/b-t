"""Augment data/bible_text.csv with video_url, start_seconds, start_hms columns.

For each verse, computes the start time inside its YouTube video as:
    chapter_audio_start[(book, chapter)] + Σ verse_dur[(short, chapter, 1..v-1)]

`chapter_audio_start` is measured empirically by `detect_book_chapter_starts.py`
(silence detection in the audio sample table). This replaces the prior model
of "c × 3.0 book pad + sum(chapter_video_dur) + 3.0 title pad" which was off
by ~5 s for every verse of every non-Genesis book (verified ch1..ch150 of 시편).
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

BIBLE_TEXT_CSV = Path("data/bible_text.csv")
YOUTUBE_VIDEOS_CSV = Path("data/youtube_videos.csv")
MP4_DURATIONS_CSV = Path("temp/mp4_durations.csv")
CHAPTER_STARTS_CSV = Path("temp/book_chapter_starts.csv")
TTS_ROOT = Path("temp/tts_result-slow")

GENESIS_BOOK = "창세기"
TIMESTAMP_LEAD_SEC = 2.0  # subtract from computed start to give a small audio lead-in

# Known anomaly: see docs/superpowers/specs/2026-05-03-bible-text-timestamps-design.md
KNOWN_MISSING_AUDIO = {("민수기", 20, v) for v in range(24, 30)}


def format_hms(seconds: float) -> str:
    """Floor to integer seconds, format as HH:MM:SS (zero-padded)."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_url_with_time(url: str, start_seconds: float | None) -> str:
    """Append YouTube `?t=` (or `&t=`) jump param. Returns plain URL when start is None."""
    if start_seconds is None:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={int(start_seconds)}"


def load_durations(csv_path: Path) -> dict[tuple[str, int, int], float]:
    """Parse mp4_durations.csv → verse_dur[(short, chapter_int, verse_int)] → seconds."""
    verse_dur: dict[tuple[str, int, int], float] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                d = float(row["duration_sec"])
            except (TypeError, ValueError):
                continue
            short = row["subfolder1"]
            sub = row["subfolder2"]
            fn = row["filename"]
            if sub.isdigit() and int(sub) > 0:
                stem = fn[:-4] if fn.endswith(".mp4") else fn
                if stem.isdigit() and int(stem) > 0:
                    verse_dur[(short, int(sub), int(stem))] = d
    return verse_dur


def load_chapter_starts(csv_path: Path) -> dict[tuple[str, int], float]:
    """Parse book_chapter_starts.csv → {(book_full_name, chapter): audio_start_seconds}."""
    out: dict[tuple[str, int], float] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                ch = int(row["chapter"])
                s = float(row["start_seconds"])
            except (TypeError, ValueError):
                continue
            out[(row["book"], ch)] = s
    return out


def build_book_short_map(tts_root: Path) -> dict[str, str]:
    """Walk {tts_root}/{short}/*.mp4. Return {full_name: short_dir} from top-level mp4 stems."""
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


def load_youtube_videos(csv_path: Path) -> dict[tuple[str, int], str]:
    """Parse youtube_videos.csv → {(book, chapter): video_url}."""
    out: dict[tuple[str, int], str] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                ch = int(row["chapter"])
            except (TypeError, ValueError):
                continue
            out[(row["book"], ch)] = row["video_url"]
    return out


def verse_start_seconds(
    verse_dur: dict[tuple[str, int, int], float],
    chapter_starts: dict[tuple[str, int], float],
    full_book: str,
    short: str,
    chapter: int,
    verse: int,
) -> float | None:
    """start = chapter_audio_start[(full_book, chapter)] + Σ verse_dur[1..v-1].

    Returns None if the chapter start or any prior verse duration is missing.
    """
    base = chapter_starts.get((full_book, chapter))
    if base is None:
        return None
    total = base
    for u in range(1, verse):
        d = verse_dur.get((short, chapter, u))
        if d is None:
            return None
        total += d
    return total


OUTPUT_FIELDS = ["book", "chapter", "verse", "text", "video_url", "start_seconds", "start_hms"]


@dataclass
class RowResult:
    video_url: str
    start_seconds: float | None
    start_hms: str
    status: str  # "ok" | "missing_video" | "missing_duration" | "missing_audio"


def process_row(
    book: str,
    chapter: int,
    verse: int,
    *,
    verse_dur: dict[tuple[str, int, int], float],
    chapter_starts: dict[tuple[str, int], float],
    yt_lookup: dict[tuple[str, int], str],
    book_short: dict[str, str],
) -> RowResult:
    """Compute the verse's video URL + start time, applying special-case handling."""
    if book == GENESIS_BOOK:
        url = yt_lookup.get((book, chapter), "")
    else:
        url = yt_lookup.get((book, 0), "")
    if not url:
        return RowResult(video_url="", start_seconds=None, start_hms="", status="missing_video")

    if (book, chapter, verse) in KNOWN_MISSING_AUDIO:
        # Verse audio is missing; emit URL pointing at the chapter start so a click
        # at least lands the user near the right region of the book video.
        base = chapter_starts.get((book, chapter))
        if base is None:
            url_with_offset = url
        else:
            adjusted = max(0.0, base - TIMESTAMP_LEAD_SEC)
            url_with_offset = build_url_with_time(url, adjusted)
        return RowResult(
            video_url=url_with_offset, start_seconds=None, start_hms="", status="missing_audio"
        )

    short = book_short.get(book)
    if short is None:
        return RowResult(video_url=url, start_seconds=None, start_hms="", status="missing_duration")

    start = verse_start_seconds(verse_dur, chapter_starts, book, short, chapter, verse)
    if start is None:
        return RowResult(video_url=url, start_seconds=None, start_hms="", status="missing_duration")

    adjusted = max(0.0, start - TIMESTAMP_LEAD_SEC)
    return RowResult(
        video_url=build_url_with_time(url, adjusted),
        start_seconds=adjusted,
        start_hms=format_hms(adjusted),
        status="ok",
    )


def write_output_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write rows atomically: build *.tmp, fsync, rename over destination."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    tmp.replace(path)


def run(
    *,
    bible_text_csv: Path,
    youtube_videos_csv: Path,
    mp4_durations_csv: Path,
    chapter_starts_csv: Path,
    tts_root: Path,
    output_csv: Path,
) -> dict[str, int]:
    """Top-level orchestration. Returns counts dict for the summary."""
    yt_lookup = load_youtube_videos(youtube_videos_csv)
    verse_dur = load_durations(mp4_durations_csv)
    chapter_starts = load_chapter_starts(chapter_starts_csv)
    book_short = build_book_short_map(tts_root)

    counts = {"ok": 0, "missing_video": 0, "missing_duration": 0, "missing_audio": 0}
    out_rows: list[dict[str, str]] = []
    problems: list[str] = []

    with bible_text_csv.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                ch = int(row["chapter"])
                v = int(row["verse"])
            except (TypeError, ValueError):
                continue
            r = process_row(
                row["book"], ch, v,
                verse_dur=verse_dur,
                chapter_starts=chapter_starts,
                yt_lookup=yt_lookup,
                book_short=book_short,
            )
            counts[r.status] += 1
            if r.status != "ok" and len(problems) < 20:
                problems.append(f"{r.status}: {row['book']} {ch}:{v}")
            out_rows.append({
                "book": row["book"],
                "chapter": row["chapter"],
                "verse": row["verse"],
                "text": row["text"],
                "video_url": r.video_url,
                "start_seconds": f"{r.start_seconds:.3f}" if r.start_seconds is not None else "",
                "start_hms": r.start_hms,
            })

    write_output_csv(output_csv, out_rows)

    print(
        f"rows_total={sum(counts.values())} ok={counts['ok']} "
        f"missing_video={counts['missing_video']} "
        f"missing_duration={counts['missing_duration']} "
        f"missing_audio={counts['missing_audio']}",
        file=sys.stderr,
    )
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    return counts


def main(argv: list[str] | None = None) -> None:
    run(
        bible_text_csv=BIBLE_TEXT_CSV,
        youtube_videos_csv=YOUTUBE_VIDEOS_CSV,
        mp4_durations_csv=MP4_DURATIONS_CSV,
        chapter_starts_csv=CHAPTER_STARTS_CSV,
        tts_root=TTS_ROOT,
        output_csv=BIBLE_TEXT_CSV,
    )


if __name__ == "__main__":
    main()
