"""Verify the YouTube → book → chapter → verse mp4 composition chain.

Runs four stages of sanity checks per book and prints a Markdown report.
Read-only: does not modify any data files.

Usage:
    python -m scripts.verify_videos                  # full check, hits YouTube
    python -m scripts.verify_videos --no-youtube     # skip stage 1 (offline)
    python -m scripts.verify_videos --book 시편       # filter to one book
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.measure_mp4_durations import mp4_duration_seconds
from scripts.detect_book_chapter_starts import build_book_short_map

YOUTUBE_VIDEOS_CSV = Path("data/youtube_videos.csv")
MP4_DURATIONS_CSV = Path("temp/mp4_durations.csv")
CHAPTER_STARTS_CSV = Path("temp/book_chapter_starts.csv")
TTS_ROOT = Path("temp/tts_result-slow")
BACKGROUND2_PATH = Path("temp/background2.mp4")
GENESIS_BOOK = "창세기"

YT_LENGTH_TOLERANCE_SEC = 1.0
BOOK_COMPOSITION_TOLERANCE_SEC = 1.0
CHAPTER_COMPOSITION_TOLERANCE_SEC = 0.15  # accommodates 176-verse 시편 ch119 (~-0.118s frame-quantisation drift)
SILENCE_GAP_TOLERANCE_SEC = 1.5  # silence between chapters varies ~7-8s; allow 1.5s slack

# Genesis chapters that are missing per-chapter mp4 (none currently, but defensive)
KNOWN_CHAPTER_COMPOSITION_EXCEPTIONS: set[tuple[str, int]] = {("민수기", 20)}  # corrupt v24-29


@dataclass
class BookReport:
    book: str
    yt_dur: float | None = None
    local_dur: float | None = None
    yt_diff: float | None = None
    book_sum_diff: float | None = None
    chapter_checks_ok: int = 0
    chapter_checks_total: int = 0
    silence_gaps_ok: bool | None = None
    notes: list[str] = field(default_factory=list)
    status: str = "OK"  # OK | WARN | FAIL


def load_youtube_videos(path: Path) -> list[tuple[str, int, str, str]]:
    out: list[tuple[str, int, str, str]] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                ch = int(r["chapter"])
            except (TypeError, ValueError):
                continue
            out.append((r["book"], ch, r.get("video_id", ""), r["video_url"]))
    return out


def load_durations(path: Path) -> tuple[dict[tuple[str, int, int], float], dict[tuple[str, int], float]]:
    verse: dict[tuple[str, int, int], float] = {}
    chap: dict[tuple[str, int], float] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                d = float(row["duration_sec"])
            except (TypeError, ValueError):
                continue
            short = row["subfolder1"]
            sub = row["subfolder2"]
            fn = row["filename"]
            if sub == "0" and fn.endswith("장.mp4"):
                stem = fn[:-4]
                if "-" in stem:
                    _, ntag = stem.rsplit("-", 1)
                    if ntag.endswith("장") and ntag[:-1].isdigit():
                        chap[(short, int(ntag[:-1]))] = d
            elif sub.isdigit() and int(sub) > 0:
                stem = fn[:-4] if fn.endswith(".mp4") else fn
                if stem.isdigit() and int(stem) > 0:
                    verse[(short, int(sub), int(stem))] = d
    return verse, chap


def load_chapter_starts(path: Path) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                ch = int(r["chapter"])
                s = float(r["start_seconds"])
            except (TypeError, ValueError):
                continue
            out[(r["book"], ch)] = s
    return out


def fetch_youtube_duration(video_id: str) -> float | None:
    """Return YouTube reported duration in seconds, or None on failure."""
    try:
        r = subprocess.run(
            ["./.venv/Scripts/yt-dlp.exe", "--no-warnings", "-J", "--skip-download",
             f"https://youtu.be/{video_id}"],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if r.returncode != 0:
            return None
        info = json.loads(r.stdout)
        d = info.get("duration")
        return float(d) if d is not None else None
    except Exception:
        return None


def check_book(
    book: str,
    short: str,
    yt_rows: list[tuple[int, str, str]],  # (chapter, video_id, url) for this book
    verse_dur: dict[tuple[str, int, int], float],
    chapter_video_dur: dict[tuple[str, int], float],
    chapter_starts: dict[tuple[str, int], float],
    *,
    fetch_youtube: bool = True,
) -> BookReport:
    rep = BookReport(book=book)
    chapters_for_short = sorted({c for (s, c) in chapter_video_dur if s == short})
    n_chapters = len(chapters_for_short)

    # -- Stage 3: chapter composition (chapter_dur ≈ 3 + Σ verse_dur)
    for c in chapters_for_short:
        cv = chapter_video_dur[(short, c)]
        sumv = sum(verse_dur.get((short, c, v), 0.0)
                   for v in range(1, max((vv for (ss, cc, vv) in verse_dur if ss == short and cc == c), default=0) + 1))
        diff = cv - (3.0 + sumv)
        if abs(diff) <= CHAPTER_COMPOSITION_TOLERANCE_SEC:
            rep.chapter_checks_ok += 1
        elif (book, c) in KNOWN_CHAPTER_COMPOSITION_EXCEPTIONS:
            rep.chapter_checks_ok += 1  # whitelisted
            rep.notes.append(f"ch{c}: composition diff {diff:+.3f} (whitelisted)")
        else:
            rep.notes.append(f"ch{c}: chapter_dur−(3+Σverse)={diff:+.3f} > {CHAPTER_COMPOSITION_TOLERANCE_SEC}")
            if rep.status != "FAIL":
                rep.status = "WARN"
        rep.chapter_checks_total += 1

    if book == GENESIS_BOOK:
        # Stage 1 + 2 are per-chapter for Genesis.
        if fetch_youtube and yt_rows:
            mismatches = 0
            for ch, vid, _ in yt_rows:
                local_mp4 = TTS_ROOT / short / "0" / f"{book}-{ch}장.mp4"
                if not local_mp4.is_file():
                    rep.notes.append(f"ch{ch}: local mp4 missing")
                    rep.status = "FAIL"
                    continue
                local = mp4_duration_seconds(local_mp4)
                yt = fetch_youtube_duration(vid)
                if yt is None:
                    rep.notes.append(f"ch{ch}: yt-dlp fetch failed")
                    if rep.status == "OK":
                        rep.status = "WARN"
                    continue
                if abs(yt - local) > YT_LENGTH_TOLERANCE_SEC:
                    rep.notes.append(f"ch{ch}: YT={yt:.0f} local={local:.3f} diff={yt-local:+.3f}")
                    mismatches += 1
            if mismatches:
                rep.status = "FAIL"
        return rep

    # -- Non-Genesis: book mp4 exists
    book_mp4 = TTS_ROOT / short / f"{book}.mp4"
    if not book_mp4.is_file():
        rep.notes.append("book mp4 missing")
        rep.status = "FAIL"
        return rep
    rep.local_dur = mp4_duration_seconds(book_mp4)

    # -- Stage 1: YouTube length vs local
    if fetch_youtube:
        yt_for_book = [r for r in yt_rows if r[0] == 0]
        if yt_for_book:
            _, vid, _ = yt_for_book[0]
            yt = fetch_youtube_duration(vid)
            if yt is None:
                rep.notes.append("yt-dlp fetch failed")
                if rep.status == "OK":
                    rep.status = "WARN"
            else:
                rep.yt_dur = yt
                rep.yt_diff = yt - rep.local_dur
                if abs(rep.yt_diff) > YT_LENGTH_TOLERANCE_SEC:
                    rep.notes.append(f"YT-local diff {rep.yt_diff:+.3f} > {YT_LENGTH_TOLERANCE_SEC}")
                    rep.status = "FAIL"

    # -- Stage 2: book ≈ Σ chapter + n × 3
    expected = sum(chapter_video_dur[(short, c)] for c in chapters_for_short) + n_chapters * 3.0
    rep.book_sum_diff = rep.local_dur - expected
    if abs(rep.book_sum_diff) > BOOK_COMPOSITION_TOLERANCE_SEC:
        rep.notes.append(f"book−(Σch+n×3)={rep.book_sum_diff:+.3f} > {BOOK_COMPOSITION_TOLERANCE_SEC}")
        if rep.status == "OK":
            rep.status = "WARN"

    # -- Stage 4: silence-detected chapter starts grow by chapter_dur + ~8s gap
    starts = [chapter_starts.get((book, c)) for c in chapters_for_short]
    if any(s is None for s in starts):
        rep.notes.append("missing chapter start(s) in temp/book_chapter_starts.csv")
        rep.silence_gaps_ok = False
        if rep.status == "OK":
            rep.status = "WARN"
    else:
        gaps_ok = True
        for i in range(len(chapters_for_short) - 1):
            c = chapters_for_short[i]
            cn = chapters_for_short[i + 1]
            actual_gap = starts[i + 1] - starts[i]
            # Audio gap = audio content of ch + inter-chapter silence (~6-8s)
            # Audio content of ch ≈ chapter_video_dur(c) - 3 (minus the video-only leading pad)
            audio_content = chapter_video_dur[(short, c)] - 3.0
            inter = actual_gap - audio_content
            if not (4.0 <= inter <= 10.0):  # generous bound; usually ~6-8s
                rep.notes.append(f"ch{c}->ch{cn}: gap={actual_gap:.3f} content={audio_content:.3f} silence={inter:.3f}")
                gaps_ok = False
        rep.silence_gaps_ok = gaps_ok
        if not gaps_ok:
            if rep.status == "OK":
                rep.status = "WARN"
    return rep


def render_report(reports: list[BookReport]) -> str:
    lines = ["| Book | YT len | Local len | Δ YT | Σ chk | Ch chk | Sil chk | Status |",
             "|---|---|---|---|---|---|---|---|"]
    for r in reports:
        yt = f"{r.yt_dur:.0f}" if r.yt_dur is not None else "—"
        local = f"{r.local_dur:.3f}" if r.local_dur is not None else "—"
        diff = f"{r.yt_diff:+.3f}" if r.yt_diff is not None else "—"
        sum_chk = (f"{r.book_sum_diff:+.3f}" if r.book_sum_diff is not None else "—")
        ch_chk = f"{r.chapter_checks_ok}/{r.chapter_checks_total}"
        sil = ("OK" if r.silence_gaps_ok else
               "—" if r.silence_gaps_ok is None else "FAIL")
        lines.append(f"| {r.book} | {yt} | {local} | {diff} | {sum_chk} | {ch_chk} | {sil} | {r.status} |")
    n_ok = sum(1 for r in reports if r.status == "OK")
    n_warn = sum(1 for r in reports if r.status == "WARN")
    n_fail = sum(1 for r in reports if r.status == "FAIL")
    lines.append("")
    lines.append(f"summary: {len(reports)} books — {n_ok} OK, {n_warn} WARN, {n_fail} FAIL")
    return "\n".join(lines)


def run(*, fetch_youtube: bool = True, books_filter: list[str] | None = None,
        yt_csv: Path = YOUTUBE_VIDEOS_CSV, dur_csv: Path = MP4_DURATIONS_CSV,
        starts_csv: Path = CHAPTER_STARTS_CSV, tts_root: Path = TTS_ROOT) -> int:
    yt_rows_all = load_youtube_videos(yt_csv)
    verse_dur, chapter_video_dur = load_durations(dur_csv)
    chapter_starts = load_chapter_starts(starts_csv)
    book_short = build_book_short_map(tts_root)

    # Background2 sanity check
    if BACKGROUND2_PATH.is_file():
        b2 = mp4_duration_seconds(BACKGROUND2_PATH)
        if abs(b2 - 3.0) > 0.01:
            print(f"warn: background2.mp4 is {b2:.3f}s (expected 3.000)", file=sys.stderr)

    # Group YouTube rows by book
    by_book: dict[str, list[tuple[int, str, str]]] = {}
    for b, c, vid, url in yt_rows_all:
        by_book.setdefault(b, []).append((c, vid, url))

    reports: list[BookReport] = []
    target_books = sorted(book_short)
    if books_filter:
        target_books = [b for b in target_books if b in set(books_filter)]
    for book in target_books:
        short = book_short[book]
        rep = check_book(
            book, short, by_book.get(book, []),
            verse_dur, chapter_video_dur, chapter_starts,
            fetch_youtube=fetch_youtube,
        )
        reports.append(rep)
        # Stream per-book status to stderr so long runs show progress
        print(f"  {rep.status:5} {rep.book}", file=sys.stderr)

    print(render_report(reports))
    return 0 if not any(r.status == "FAIL" for r in reports) else 1


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-youtube", action="store_true", help="skip YouTube fetch")
    p.add_argument("--book", action="append", help="limit to listed book(s); repeatable")
    args = p.parse_args()
    rc = run(fetch_youtube=not args.no_youtube, books_filter=args.book)
    sys.exit(rc)


if __name__ == "__main__":
    main()
