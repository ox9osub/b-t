"""Tests for scripts.build_verse_timestamps."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import build_verse_timestamps as bvt


def test_format_hms_zero():
    assert bvt.format_hms(0.0) == "00:00:00"


def test_format_hms_truncates_fractional():
    assert bvt.format_hms(83.7) == "00:01:23"


def test_format_hms_one_hour_one_minute_one_second():
    assert bvt.format_hms(3661.0) == "01:01:01"


def test_format_hms_overflow_24h_does_not_wrap():
    # Bible book videos can exceed 5h but never 24h; format must still be sensible.
    assert bvt.format_hms(36_000.0) == "10:00:00"


def test_build_url_with_time_basic():
    url = bvt.build_url_with_time("https://youtu.be/abc", 83.456)
    assert url == "https://youtu.be/abc?t=83"


def test_build_url_with_time_zero():
    url = bvt.build_url_with_time("https://youtu.be/abc", 0.0)
    assert url == "https://youtu.be/abc?t=0"


def test_build_url_with_time_existing_query_param():
    url = bvt.build_url_with_time("https://youtu.be/abc?si=foo", 12.0)
    assert url == "https://youtu.be/abc?si=foo&t=12"


def test_build_url_without_time_returns_url_unchanged():
    """When start time is None (missing), return URL with no jump param."""
    assert bvt.build_url_with_time("https://youtu.be/abc", None) == "https://youtu.be/abc"


def test_build_book_short_map(tmp_path: Path):
    # tmp_path/창/창세기.mp4
    (tmp_path / "창").mkdir()
    (tmp_path / "창" / "창세기.mp4").write_bytes(b"\x00")
    # tmp_path/유/유다서.mp4
    (tmp_path / "유").mkdir()
    (tmp_path / "유" / "유다서.mp4").write_bytes(b"\x00")
    # tmp_path/empty/   (dir with no mp4 — should be skipped)
    (tmp_path / "empty").mkdir()
    # tmp_path/요1/0/   (dir with only a subdir — should be skipped, no top-level mp4)
    (tmp_path / "요1" / "0").mkdir(parents=True)

    result = bvt.build_book_short_map(tmp_path)
    assert result == {"창세기": "창", "유다서": "유"}


def test_build_book_short_map_returns_empty_when_root_missing(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    assert bvt.build_book_short_map(missing) == {}


def test_load_durations_parses_verses_and_chapters(tmp_path: Path):
    csv_path = tmp_path / "durations.csv"
    csv_path.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,창,0,0.mp4,1.000\n"
        "tts_result-slow,창,0,창세기-1장.mp4,340.208\n"
        "tts_result-slow,창,1,0.mp4,1.000\n"
        "tts_result-slow,창,1,1.mp4,5.557\n"
        "tts_result-slow,창,1,2.mp4,9.779\n"
        "tts_result-slow,갈,0,갈라디아서-1장.mp4,254.235\n",
        encoding="utf-8-sig",
    )
    verse_dur, chapter_video_dur = bvt.load_durations(csv_path)

    assert verse_dur[("창", 1, 1)] == 5.557
    assert verse_dur[("창", 1, 2)] == 9.779
    assert ("창", 1, 0) not in verse_dur  # 0.mp4 is not a verse
    assert chapter_video_dur[("창", 1)] == 340.208
    assert chapter_video_dur[("갈", 1)] == 254.235


def test_load_durations_skips_empty_duration(tmp_path: Path):
    csv_path = tmp_path / "durations.csv"
    csv_path.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,민,20,24.mp4,\n"  # broken file: empty duration
        "tts_result-slow,민,20,25.mp4,7.176\n",
        encoding="utf-8-sig",
    )
    verse_dur, _ = bvt.load_durations(csv_path)
    assert ("민", 20, 24) not in verse_dur
    assert verse_dur[("민", 20, 25)] == 7.176
