"""Augment data/bible_text.csv with video_url, start_seconds, start_hms columns.

For each verse, computes the start time inside its YouTube video by summing
local mp4 durations using a verified concat formula:
  - chapter_video = 3.0s title pad + verse mp4s
  - book_video    = sum(chapter_videos) + n × 3.0s pads (book intro + per-chapter)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

BIBLE_TEXT_CSV = Path("data/bible_text.csv")
YOUTUBE_VIDEOS_CSV = Path("data/youtube_videos.csv")
MP4_DURATIONS_CSV = Path("temp/mp4_durations.csv")
TTS_ROOT = Path("temp/tts_result-slow")

CHAPTER_TITLE_PAD_SEC = 3.0  # background2 leading pad inside each chapter video
BOOK_GAP_PAD_SEC = 3.0       # background2 between chapter videos in book videos
GENESIS_BOOK = "창세기"

# Known anomaly: see docs/superpowers/specs/2026-05-03-bible-text-timestamps-design.md
KNOWN_MISSING_AUDIO = {("민수기", 20, v) for v in range(24, 30)}


def format_hms(seconds: float) -> str:
    """Floor to integer seconds, format as HH:MM:SS (zero-padded)."""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
