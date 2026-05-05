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
    (tmp_path / "창").mkdir()
    (tmp_path / "창" / "창세기.mp4").write_bytes(b"\x00")
    (tmp_path / "유").mkdir()
    (tmp_path / "유" / "유다서.mp4").write_bytes(b"\x00")
    (tmp_path / "empty").mkdir()
    (tmp_path / "요1" / "0").mkdir(parents=True)

    result = bvt.build_book_short_map(tmp_path)
    assert result == {"창세기": "창", "유다서": "유"}


def test_build_book_short_map_returns_empty_when_root_missing(tmp_path: Path):
    missing = tmp_path / "does_not_exist"
    assert bvt.build_book_short_map(missing) == {}


def test_load_durations_parses_verses(tmp_path: Path):
    csv_path = tmp_path / "durations.csv"
    csv_path.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,창,0,0.mp4,1.000\n"
        "tts_result-slow,창,0,창세기-1장.mp4,340.208\n"
        "tts_result-slow,창,1,0.mp4,1.000\n"
        "tts_result-slow,창,1,1.mp4,5.557\n"
        "tts_result-slow,창,1,2.mp4,9.779\n",
        encoding="utf-8-sig",
    )
    verse_dur = bvt.load_durations(csv_path)
    assert verse_dur[("창", 1, 1)] == 5.557
    assert verse_dur[("창", 1, 2)] == 9.779
    # 0.mp4 spacers and per-chapter videos are not verses
    assert ("창", 1, 0) not in verse_dur


def test_load_durations_skips_empty_duration(tmp_path: Path):
    csv_path = tmp_path / "durations.csv"
    csv_path.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,민,20,24.mp4,\n"  # broken file: empty duration
        "tts_result-slow,민,20,25.mp4,7.176\n",
        encoding="utf-8-sig",
    )
    verse_dur = bvt.load_durations(csv_path)
    assert ("민", 20, 24) not in verse_dur
    assert verse_dur[("민", 20, 25)] == 7.176


def test_load_chapter_starts(tmp_path: Path):
    csv_path = tmp_path / "starts.csv"
    csv_path.write_text(
        "book,chapter,start_seconds\n"
        "창세기,1,0.998\n"
        "창세기,2,0.998\n"
        "갈라디아서,1,0.998\n"
        "갈라디아서,2,258.232\n",
        encoding="utf-8-sig",
    )
    cs = bvt.load_chapter_starts(csv_path)
    assert cs[("창세기", 1)] == 0.998
    assert cs[("갈라디아서", 2)] == 258.232


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


def test_verse_start_first_verse_uses_chapter_audio_start():
    verse_dur = {("갈", 1, 1): 17.470}
    chapter_starts = {("갈라디아서", 1): 0.998}
    assert bvt.verse_start_seconds(
        verse_dur, chapter_starts, "갈라디아서", "갈", 1, 1
    ) == pytest.approx(0.998)


def test_verse_start_third_verse_adds_prior_durations():
    verse_dur = {
        ("갈", 1, 1): 17.470,
        ("갈", 1, 2): 18.135,
        ("갈", 1, 3): 8.593,
    }
    chapter_starts = {("갈라디아서", 1): 0.998}
    expected = 0.998 + 17.470 + 18.135
    assert bvt.verse_start_seconds(
        verse_dur, chapter_starts, "갈라디아서", "갈", 1, 3
    ) == pytest.approx(expected)


def test_verse_start_genesis_uses_per_chapter_start():
    verse_dur = {("창", 5, 1): 4.123, ("창", 5, 2): 6.789}
    chapter_starts = {("창세기", 5): 1.234}
    expected = 1.234 + 4.123
    assert bvt.verse_start_seconds(
        verse_dur, chapter_starts, "창세기", "창", 5, 2
    ) == pytest.approx(expected)


def test_verse_start_returns_none_when_chapter_start_missing():
    verse_dur = {("갈", 1, 1): 17.470}
    chapter_starts: dict[tuple[str, int], float] = {}
    assert bvt.verse_start_seconds(
        verse_dur, chapter_starts, "갈라디아서", "갈", 1, 1
    ) is None


def test_verse_start_returns_none_when_prior_verse_dur_missing():
    verse_dur = {("갈", 1, 1): 17.470, ("갈", 1, 3): 8.593}  # v2 missing
    chapter_starts = {("갈라디아서", 1): 0.998}
    assert bvt.verse_start_seconds(
        verse_dur, chapter_starts, "갈라디아서", "갈", 1, 3
    ) is None


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
        "chapter_starts": {
            ("창세기", 1): 0.998,
            ("갈라디아서", 1): 0.998,
            ("갈라디아서", 2): 258.232,
            ("민수기", 20): 7958.194,
        },
        "yt_lookup": {
            ("창세기", 1): "https://youtu.be/gen1",
            ("갈라디아서", 0): "https://youtu.be/gal",
            ("민수기", 0): "https://youtu.be/num",
        },
        "book_short": {"창세기": "창", "갈라디아서": "갈", "민수기": "민"},
    }


def test_process_row_genesis_first_verse(small_corpus):
    """Verse 1 of Genesis ch1: chapter audio starts at 0.998s; URL drops 2s lead → 0."""
    result = bvt.process_row("창세기", 1, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gen1?t=0"
    assert result.start_seconds == pytest.approx(0.0)  # max(0, 0.998 - 2) = 0
    assert result.start_hms == "00:00:00"
    assert result.status == "ok"


def test_process_row_other_book_first_verse(small_corpus):
    """갈라디아서 1:1: chapter audio starts at 0.998s in book; URL drops 2s lead → 0."""
    result = bvt.process_row("갈라디아서", 1, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gal?t=0"
    assert result.start_seconds == pytest.approx(0.0)
    assert result.start_hms == "00:00:00"
    assert result.status == "ok"


def test_process_row_other_book_chapter_2_verse_1(small_corpus):
    """갈라디아서 2:1: uses ch2 audio start (258.232) - 2s lead = 256.232."""
    result = bvt.process_row("갈라디아서", 2, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gal?t=256"
    assert result.start_seconds == pytest.approx(256.232)
    assert result.start_hms == "00:04:16"
    assert result.status == "ok"


def test_process_row_missing_video_book(small_corpus):
    result = bvt.process_row("토비트", 1, 1, **small_corpus)
    assert result.video_url == ""
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_video"


def test_process_row_missing_audio_known_anomaly(small_corpus):
    """민수기 20:24 — known broken; URL gets chapter offset (?t=...) but timestamp empty."""
    result = bvt.process_row("민수기", 20, 24, **small_corpus)
    # chapter_starts[(민수기, 20)] = 7958.194; lead = 2 → adjusted = 7956.194 → int = 7956
    assert result.video_url == "https://youtu.be/num?t=7956"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_audio"


def test_process_row_missing_audio_falls_back_when_chapter_start_missing(small_corpus):
    small_corpus = {**small_corpus, "chapter_starts": {}}
    result = bvt.process_row("민수기", 20, 24, **small_corpus)
    assert result.video_url == "https://youtu.be/num"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_audio"


def test_process_row_missing_duration_propagates(small_corpus):
    """Galatians ch1 verse 3: prior verse 2 missing in fixture → start cannot be computed."""
    small_corpus["verse_dur"] = {**small_corpus["verse_dur"], ("갈", 1, 3): 9.345}
    result = bvt.process_row("갈라디아서", 1, 3, **small_corpus)
    assert result.video_url == "https://youtu.be/gal"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_duration"


def test_write_output_csv_atomic(tmp_path: Path):
    out = tmp_path / "out.csv"
    rows = [
        {"book": "창세기", "chapter": "1", "verse": "1", "text": "태초에",
         "video_url": "https://youtu.be/gen1?t=0", "start_seconds": "0.000", "start_hms": "00:00:00"},
        {"book": "창세기", "chapter": "1", "verse": "2", "text": "땅이",
         "video_url": "https://youtu.be/gen1?t=4", "start_seconds": "4.557", "start_hms": "00:00:04"},
    ]
    bvt.write_output_csv(out, rows)
    text = out.read_text(encoding="utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "book,chapter,verse,text,video_url,start_seconds,start_hms"
    assert lines[1].startswith("창세기,1,1,태초에,")
    assert not (out.parent / (out.name + ".tmp")).exists()


def test_write_output_csv_overwrites_existing(tmp_path: Path):
    out = tmp_path / "out.csv"
    out.write_text("garbage\n", encoding="utf-8")
    bvt.write_output_csv(
        out,
        [{"book": "유다서", "chapter": "1", "verse": "1", "text": "x",
          "video_url": "https://y/1", "start_seconds": "1.000", "start_hms": "00:00:01"}],
    )
    assert "garbage" not in out.read_text(encoding="utf-8-sig")


def test_run_end_to_end_synthetic(tmp_path: Path):
    """Synthetic full pipeline: bible_text + youtube + durations + chapter_starts → output."""
    bible = tmp_path / "bible_text.csv"
    bible.write_text(
        "book,chapter,verse,text\n"
        "창세기,1,1,태초에\n"
        "창세기,1,2,땅이\n"
        "유다서,1,1,예수의\n",
        encoding="utf-8-sig",
    )
    yt = tmp_path / "yt.csv"
    yt.write_text(
        "book,chapter,video_id,video_url,title\n"
        "창세기,1,gen1,https://youtu.be/gen1,창세기 1장\n"
        "유다서,0,jud,https://youtu.be/jud,유다서 [오디오]\n",
        encoding="utf-8",
    )
    dur = tmp_path / "dur.csv"
    dur.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,창,1,1.mp4,5.557\n"
        "tts_result-slow,창,1,2.mp4,9.779\n"
        "tts_result-slow,유,1,1.mp4,17.037\n",
        encoding="utf-8-sig",
    )
    starts = tmp_path / "starts.csv"
    starts.write_text(
        "book,chapter,start_seconds\n"
        "창세기,1,0.998\n"
        "유다서,1,0.998\n",
        encoding="utf-8-sig",
    )
    tts_root = tmp_path / "tts"
    (tts_root / "창").mkdir(parents=True)
    (tts_root / "창" / "창세기.mp4").write_bytes(b"\x00")
    (tts_root / "유").mkdir()
    (tts_root / "유" / "유다서.mp4").write_bytes(b"\x00")

    summary = bvt.run(
        bible_text_csv=bible,
        youtube_videos_csv=yt,
        mp4_durations_csv=dur,
        chapter_starts_csv=starts,
        tts_root=tts_root,
        output_csv=bible,
    )

    out_rows = list(csv.DictReader(bible.open(encoding="utf-8-sig")))
    assert len(out_rows) == 3
    # 창세기 1:1 → 0.998 - 2 = max(0,-1) = 0 → URL t=0
    assert out_rows[0]["video_url"] == "https://youtu.be/gen1?t=0"
    assert out_rows[0]["start_seconds"] == "0.000"
    assert out_rows[0]["start_hms"] == "00:00:00"
    # 창세기 1:2 → 0.998 + 5.557 - 2 = 4.555 → URL t=4
    assert out_rows[1]["start_seconds"] == "4.555"
    assert out_rows[1]["video_url"] == "https://youtu.be/gen1?t=4"
    # 유다서 1:1 → 0.998 - 2 = max(0,-1) = 0
    assert out_rows[2]["video_url"] == "https://youtu.be/jud?t=0"
    assert out_rows[2]["start_seconds"] == "0.000"
    assert summary["ok"] == 3
    assert summary["missing_video"] == 0
    assert summary["missing_duration"] == 0
    assert summary["missing_audio"] == 0


REAL_BIBLE = Path("data/bible_text.csv")
REAL_YT = Path("data/youtube_videos.csv")
REAL_DUR = Path("temp/mp4_durations.csv")
REAL_STARTS = Path("temp/book_chapter_starts.csv")
REAL_TTS = Path("temp/tts_result-slow")


@pytest.mark.skipif(
    not all(p.exists() for p in [REAL_BIBLE, REAL_YT, REAL_DUR, REAL_STARTS, REAL_TTS]),
    reason="real corpus files not present",
)
def test_smoke_real_corpus(tmp_path: Path):
    """Run the script on real data; verify a handful of known timestamps."""
    out = tmp_path / "out.csv"
    counts = bvt.run(
        bible_text_csv=REAL_BIBLE,
        youtube_videos_csv=REAL_YT,
        mp4_durations_csv=REAL_DUR,
        chapter_starts_csv=REAL_STARTS,
        tts_root=REAL_TTS,
        output_csv=out,
    )
    assert counts["ok"] > 30000  # full Bible has ~31k verses

    rows_by_key = {}
    with out.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows_by_key[(r["book"], r["chapter"], r["verse"])] = r

    # Genesis 1:1 — chapter audio starts ~0.998s; URL t=0 (with 2s lead clamp)
    g11 = rows_by_key[("창세기", "1", "1")]
    assert g11["start_hms"] == "00:00:00"
    assert "?t=0" in g11["video_url"]

    # 갈라디아서 1:1 — same first-audio onset pattern, URL t=0
    gal11 = rows_by_key[("갈라디아서", "1", "1")]
    assert gal11["start_hms"] == "00:00:00"
    assert "?t=0" in gal11["video_url"]

    # 시편 127:3 — must align with user-reported real position ~21300s
    p127_3 = rows_by_key[("시편", "127", "3")]
    assert "21298" in p127_3["video_url"] or "21299" in p127_3["video_url"]

    # 마태복음 18:3 — must align with user-reported real position ~6320s
    m18_3 = rows_by_key[("마태복음", "18", "3")]
    assert "6318" in m18_3["video_url"] or "6319" in m18_3["video_url"] or "6320" in m18_3["video_url"]

    # 민수기 20:24 — known anomaly; no timestamp but URL has chapter offset
    n2024 = rows_by_key[("민수기", "20", "24")]
    assert n2024["start_seconds"] == ""
    assert n2024["start_hms"] == ""
    assert "?t=" in n2024["video_url"]

    assert counts["missing_audio"] == 6
