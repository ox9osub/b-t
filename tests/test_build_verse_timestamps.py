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


def test_load_youtube_videos(tmp_path: Path):
    csv_path = tmp_path / "yt.csv"
    csv_path.write_text(
        "book,chapter,video_id,video_url,title\n"
        "창세기,1,abc111,https://youtu.be/abc111,창세기 1장\n"
        "창세기,2,abc222,https://youtu.be/abc222,창세기 2장\n"
        "유다서,0,jud000,https://youtu.be/jud000,유다서 [오디오 성경]\n",
        encoding="utf-8",
    )
    yt = bvt.load_youtube_videos(csv_path)
    assert yt[("창세기", 1)] == "https://youtu.be/abc111"
    assert yt[("창세기", 2)] == "https://youtu.be/abc222"
    assert yt[("유다서", 0)] == "https://youtu.be/jud000"


def test_genesis_start_seconds_first_verse():
    verse_dur = {("창", 1, 1): 5.557, ("창", 1, 2): 9.779, ("창", 1, 3): 6.772}
    # Verse 1: just the 3 sec chapter title pad in front
    assert bvt.genesis_start_seconds(verse_dur, "창", 1, 1) == 3.0


def test_genesis_start_seconds_third_verse():
    verse_dur = {("창", 1, 1): 5.557, ("창", 1, 2): 9.779, ("창", 1, 3): 6.772}
    # Verse 3: 3 + verse1 + verse2
    assert bvt.genesis_start_seconds(verse_dur, "창", 1, 3) == pytest.approx(
        3.0 + 5.557 + 9.779
    )


def test_genesis_start_seconds_missing_prior_verse_returns_none():
    # Verse 2 mp4 is missing — verse 3's offset cannot be computed
    verse_dur = {("창", 1, 1): 5.557, ("창", 1, 3): 6.772}
    assert bvt.genesis_start_seconds(verse_dur, "창", 1, 3) is None


def test_book_start_seconds_chapter_1_verse_1_has_book_intro_offset():
    """A model: book = [3s intro] + ch1_video + [3s] + ch2_video + ...
    So ch1 starts at 3s in book; verse 1 is preceded by chapter title pad → 6s."""
    verse_dur = {("갈", 1, 1): 17.470}
    chapter_video_dur = {("갈", 1): 254.235}
    assert bvt.book_start_seconds(
        verse_dur, chapter_video_dur, "갈", 1, 1
    ) == pytest.approx(3.0 + 3.0)


def test_book_start_seconds_chapter_2_verse_1():
    """ch2 starts after [3s intro][ch1_video][3s gap]; verse 1 then has its own 3s title pad."""
    verse_dur = {("갈", 1, 1): 17.470, ("갈", 2, 1): 8.680}
    chapter_video_dur = {("갈", 1): 254.235, ("갈", 2): 293.404}
    expected = 2 * 3.0 + 254.235 + 3.0
    assert bvt.book_start_seconds(
        verse_dur, chapter_video_dur, "갈", 2, 1
    ) == pytest.approx(expected)


def test_book_start_seconds_chapter_2_verse_3():
    """Verse 3 of chapter 2: chapter offset + chapter title + verse1 + verse2."""
    verse_dur = {
        ("갈", 1, 1): 17.470,
        ("갈", 2, 1): 8.680,
        ("갈", 2, 2): 18.135,
        ("갈", 2, 3): 8.593,
    }
    chapter_video_dur = {("갈", 1): 254.235, ("갈", 2): 293.404}
    expected = 2 * 3.0 + 254.235 + 3.0 + 8.680 + 18.135
    assert bvt.book_start_seconds(
        verse_dur, chapter_video_dur, "갈", 2, 3
    ) == pytest.approx(expected)


def test_book_start_seconds_missing_prior_chapter_returns_none():
    verse_dur = {("갈", 2, 1): 8.680}
    chapter_video_dur = {("갈", 2): 293.404}  # ch1 dur missing
    assert bvt.book_start_seconds(verse_dur, chapter_video_dur, "갈", 2, 1) is None


def test_book_start_seconds_missing_prior_verse_returns_none():
    verse_dur = {("갈", 1, 1): 17.470, ("갈", 1, 3): 9.345}  # v2 missing
    chapter_video_dur = {("갈", 1): 254.235}
    assert bvt.book_start_seconds(verse_dur, chapter_video_dur, "갈", 1, 3) is None


@pytest.fixture
def small_corpus():
    """Synthetic data covering Genesis chapter-video and a 2-chapter book."""
    return {
        "verse_dur": {
            ("창", 1, 1): 5.557,
            ("창", 1, 2): 9.779,
            ("갈", 1, 1): 17.470,
            ("갈", 2, 1): 8.680,
            # 민수기 20 — verse 24 missing (broken file in real data)
            ("민", 20, 23): 9.258,
            ("민", 20, 25): 7.176,
        },
        "chapter_video_dur": {
            ("창", 1): 340.208,
            ("갈", 1): 254.235,
            ("갈", 2): 293.404,
        },
        "yt_lookup": {
            ("창세기", 1): "https://youtu.be/gen1",
            ("갈라디아서", 0): "https://youtu.be/gal",
            ("민수기", 0): "https://youtu.be/num",
        },
        "book_short": {"창세기": "창", "갈라디아서": "갈", "민수기": "민"},
    }


def test_process_row_genesis_first_verse(small_corpus):
    result = bvt.process_row("창세기", 1, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gen1?t=3"
    assert result.start_seconds == pytest.approx(3.0)
    assert result.start_hms == "00:00:03"
    assert result.status == "ok"


def test_process_row_other_book_first_verse(small_corpus):
    result = bvt.process_row("갈라디아서", 1, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gal?t=6"
    assert result.start_seconds == pytest.approx(6.0)
    assert result.start_hms == "00:00:06"
    assert result.status == "ok"


def test_process_row_missing_video_book(small_corpus):
    # Book not in yt_lookup
    result = bvt.process_row("토비트", 1, 1, **small_corpus)
    assert result.video_url == ""
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_video"


def test_process_row_missing_audio_known_anomaly(small_corpus):
    # 민수기 20:24 — known broken; emit URL without ?t=, empty timestamp, status missing_audio
    result = bvt.process_row("민수기", 20, 24, **small_corpus)
    assert result.video_url == "https://youtu.be/num"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_audio"


def test_process_row_missing_duration_propagates(small_corpus):
    """Galatians ch1 verse 3: prior verse 2 missing in fixture, no known-audio anomaly here.
    The cumulative-sum formula should fail and return missing_duration."""
    # Add a missing-verse setup to the fixture data on the fly
    small_corpus["verse_dur"] = {**small_corpus["verse_dur"], ("갈", 1, 3): 9.345}
    # Note: ("갈", 1, 2) is intentionally NOT in verse_dur, so v3 cannot be computed
    result = bvt.process_row("갈라디아서", 1, 3, **small_corpus)
    assert result.video_url == "https://youtu.be/gal"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_duration"
