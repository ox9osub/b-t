"""Augment data/bible_text.csv with video_url, start_seconds, start_hms columns.

For each verse, computes the start time inside its YouTube video by summing
local mp4 durations using a verified concat formula:
  - chapter_video = 3.0s title pad + verse mp4s
  - book_video    = sum(chapter_videos) + n × 3.0s pads (book intro + per-chapter)
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

BIBLE_TEXT_CSV = Path("data/bible_text.csv")
YOUTUBE_VIDEOS_CSV = Path("data/youtube_videos.csv")
MP4_DURATIONS_CSV = Path("temp/mp4_durations.csv")
TTS_ROOT = Path("temp/tts_result-slow")

CHAPTER_TITLE_PAD_SEC = 3.0  # background2 leading pad inside each chapter video
BOOK_GAP_PAD_SEC = 3.0       # background2 between chapter videos in book videos
GENESIS_BOOK = "창세기"

# Known anomaly: see docs/superpowers/specs/2026-05-03-bible-text-timestamps-design.md
KNOWN_MISSING_AUDIO = {("민수기", 20, 24)}


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


def load_durations(
    csv_path: Path,
) -> tuple[dict[tuple[str, int, int], float], dict[tuple[str, int], float]]:
    """Parse mp4_durations.csv → (verse_dur, chapter_video_dur).

    verse_dur:         (short, chapter_int, verse_int) → seconds (excludes verse 0 / spacers)
    chapter_video_dur: (short, chapter_int) → seconds (the per-chapter book mp4)
    """
    verse_dur: dict[tuple[str, int, int], float] = {}
    chapter_video_dur: dict[tuple[str, int], float] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                d = float(row["duration_sec"])
            except (TypeError, ValueError):
                continue  # empty / malformed — skip silently; missing-handling is downstream
            short = row["subfolder1"]
            sub = row["subfolder2"]
            fn = row["filename"]
            if sub == "0" and fn.endswith("장.mp4"):
                stem = fn[:-4]
                if "-" not in stem:
                    continue
                _, ntag = stem.rsplit("-", 1)
                if ntag.endswith("장") and ntag[:-1].isdigit():
                    chapter_video_dur[(short, int(ntag[:-1]))] = d
            elif sub.isdigit() and int(sub) > 0:
                stem = fn[:-4] if fn.endswith(".mp4") else fn
                if stem.isdigit() and int(stem) > 0:
                    verse_dur[(short, int(sub), int(stem))] = d
    return verse_dur, chapter_video_dur


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


def genesis_start_seconds(
    verse_dur: dict[tuple[str, int, int], float],
    short: str,
    chapter: int,
    verse: int,
) -> float | None:
    """Genesis: chapter-video start = 3.0 chapter title + sum(prior verses).

    Returns None if any prior verse duration is missing.
    """
    total = CHAPTER_TITLE_PAD_SEC
    for u in range(1, verse):
        d = verse_dur.get((short, chapter, u))
        if d is None:
            return None
        total += d
    return total


def book_start_seconds(
    verse_dur: dict[tuple[str, int, int], float],
    chapter_video_dur: dict[tuple[str, int], float],
    short: str,
    chapter: int,
    verse: int,
) -> float | None:
    """A model: book_video = [3s intro] + ch1_video + [3s] + ch2_video + ... + [3s] + chN_video.

    chapter_offset(c) = c × 3.0 + Σ_{j=1..c-1} chapter_video_dur[(short, j)]
    start            = chapter_offset(c) + 3.0 chapter_title_pad + Σ_{u=1..v-1} verse_dur[u]

    Returns None if any prior chapter video duration or prior verse duration is missing.
    """
    chapter_offset = chapter * BOOK_GAP_PAD_SEC
    for j in range(1, chapter):
        d = chapter_video_dur.get((short, j))
        if d is None:
            return None
        chapter_offset += d
    total = chapter_offset + CHAPTER_TITLE_PAD_SEC
    for u in range(1, verse):
        d = verse_dur.get((short, chapter, u))
        if d is None:
            return None
        total += d
    return total


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
    chapter_video_dur: dict[tuple[str, int], float],
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
        return RowResult(
            video_url=url, start_seconds=None, start_hms="", status="missing_audio"
        )

    short = book_short.get(book)
    if short is None:
        return RowResult(video_url=url, start_seconds=None, start_hms="", status="missing_duration")

    if book == GENESIS_BOOK:
        start = genesis_start_seconds(verse_dur, short, chapter, verse)
    else:
        start = book_start_seconds(verse_dur, chapter_video_dur, short, chapter, verse)

    if start is None:
        return RowResult(video_url=url, start_seconds=None, start_hms="", status="missing_duration")

    return RowResult(
        video_url=build_url_with_time(url, start),
        start_seconds=start,
        start_hms=format_hms(start),
        status="ok",
    )
