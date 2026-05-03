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
    assert result.video_url == "https://youtu.be/gen1?t=1"
    assert result.start_seconds == pytest.approx(1.0)
    assert result.start_hms == "00:00:01"
    assert result.status == "ok"


def test_process_row_other_book_first_verse(small_corpus):
    result = bvt.process_row("갈라디아서", 1, 1, **small_corpus)
    assert result.video_url == "https://youtu.be/gal?t=4"
    assert result.start_seconds == pytest.approx(4.0)
    assert result.start_hms == "00:00:04"
    assert result.status == "ok"


def test_process_row_missing_video_book(small_corpus):
    # Book not in yt_lookup
    result = bvt.process_row("토비트", 1, 1, **small_corpus)
    assert result.video_url == ""
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_video"


def test_process_row_missing_audio_known_anomaly(small_corpus):
    # 민수기 20:24 — known broken; URL gets chapter offset (?t=...) but timestamp empty
    # Add synthetic chapter durations for 민수기 ch1..19 so chapter_offset can be computed.
    small_corpus = {**small_corpus}
    small_corpus["chapter_video_dur"] = {
        **small_corpus["chapter_video_dur"],
        **{("민", j): 100.0 for j in range(1, 20)},  # 19 dummy chapter durations
    }
    result = bvt.process_row("민수기", 20, 24, **small_corpus)
    # chapter_offset(20) = 20*3 + 19*100 = 60 + 1900 = 1960
    # adjusted = max(0, 1960 - 2) = 1958
    assert result.video_url == "https://youtu.be/num?t=1958"
    assert result.start_seconds is None
    assert result.start_hms == ""
    assert result.status == "missing_audio"


def test_process_row_missing_audio_falls_back_when_chapter_dur_missing(small_corpus):
    # If chapter durations are unknown, we cannot compute the chapter offset,
    # so fall back to the bare URL.
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


def test_write_output_csv_atomic(tmp_path: Path):
    out = tmp_path / "out.csv"
    rows = [
        {
            "book": "창세기",
            "chapter": "1",
            "verse": "1",
            "text": "태초에",
            "video_url": "https://youtu.be/gen1?t=3",
            "start_seconds": "3.000",
            "start_hms": "00:00:03",
        },
        {
            "book": "창세기",
            "chapter": "1",
            "verse": "2",
            "text": "땅이",
            "video_url": "https://youtu.be/gen1?t=8",
            "start_seconds": "8.557",
            "start_hms": "00:00:08",
        },
    ]
    bvt.write_output_csv(out, rows)
    text = out.read_text(encoding="utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0] == "book,chapter,verse,text,video_url,start_seconds,start_hms"
    assert lines[1].startswith("창세기,1,1,태초에,")
    # tmp file removed
    assert not (out.parent / (out.name + ".tmp")).exists()


def test_write_output_csv_overwrites_existing(tmp_path: Path):
    out = tmp_path / "out.csv"
    out.write_text("garbage\n", encoding="utf-8")
    bvt.write_output_csv(
        out,
        [
            {
                "book": "유다서",
                "chapter": "1",
                "verse": "1",
                "text": "x",
                "video_url": "https://y/1",
                "start_seconds": "1.000",
                "start_hms": "00:00:01",
            }
        ],
    )
    assert "garbage" not in out.read_text(encoding="utf-8-sig")


def test_run_end_to_end_synthetic(tmp_path: Path, monkeypatch):
    """Synthetic full pipeline: bible_text + youtube + durations + tts_root → output."""
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
        "tts_result-slow,창,0,창세기-1장.mp4,340.208\n"
        "tts_result-slow,유,1,1.mp4,17.037\n"
        "tts_result-slow,유,0,유다서-1장.mp4,342.230\n",
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
        tts_root=tts_root,
        output_csv=bible,
    )

    out_rows = list(csv.DictReader(bible.open(encoding="utf-8-sig")))
    assert len(out_rows) == 3
    assert out_rows[0]["video_url"] == "https://youtu.be/gen1?t=1"
    assert out_rows[0]["start_seconds"] == "1.000"
    assert out_rows[0]["start_hms"] == "00:00:01"
    assert out_rows[1]["start_seconds"] == "6.557"  # 3 + 5.557 - 2
    # 유다서 1:1 — book video, ch1 only: chapter_offset = 1*3 + 0 = 3, + 3 (title) = 6, -2 = 4
    assert out_rows[2]["video_url"] == "https://youtu.be/jud?t=4"
    assert out_rows[2]["start_seconds"] == "4.000"
    assert summary["ok"] == 3
    assert summary["missing_video"] == 0
    assert summary["missing_duration"] == 0
    assert summary["missing_audio"] == 0


def test_verify_book_durations_passes_when_consistent(capsys):
    chapter_video_dur = {("갈", 1): 254.235, ("갈", 2): 293.404}
    measured = {"갈라디아서": 2 * 3.0 + 254.235 + 293.404}  # exact
    book_short = {"갈라디아서": "갈"}
    ok = bvt.verify_book_durations(chapter_video_dur, measured, book_short, tolerance=1.0)
    assert ok is True


def test_verify_book_durations_warns_on_drift(capsys):
    chapter_video_dur = {("갈", 1): 254.235}
    measured = {"갈라디아서": 100.0}  # way off
    book_short = {"갈라디아서": "갈"}
    ok = bvt.verify_book_durations(chapter_video_dur, measured, book_short, tolerance=1.0)
    assert ok is False
    err = capsys.readouterr().err
    assert "갈라디아서" in err


REAL_BIBLE = Path("data/bible_text.csv")
REAL_YT = Path("data/youtube_videos.csv")
REAL_DUR = Path("temp/mp4_durations.csv")
REAL_TTS = Path("temp/tts_result-slow")


@pytest.mark.skipif(
    not all(p.exists() for p in [REAL_BIBLE, REAL_YT, REAL_DUR, REAL_TTS]),
    reason="real corpus files not present",
)
def test_smoke_real_corpus(tmp_path: Path):
    """Run the script on real data; verify a handful of known timestamps."""
    out = tmp_path / "out.csv"
    counts = bvt.run(
        bible_text_csv=REAL_BIBLE,
        youtube_videos_csv=REAL_YT,
        mp4_durations_csv=REAL_DUR,
        tts_root=REAL_TTS,
        output_csv=out,
    )
    assert counts["ok"] > 30000  # full Bible has ~31k verses

    rows_by_key = {}
    with out.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows_by_key[(r["book"], r["chapter"], r["verse"])] = r

    # Genesis 1:1 — chapter video starts with 3s pad, minus 2s lead = 1s
    g11 = rows_by_key[("창세기", "1", "1")]
    assert g11["start_hms"] == "00:00:01"
    assert "?t=1" in g11["video_url"]

    # 갈라디아서 1:1 — book video, A model: 2*3 + 0 = 6 sec, minus 2s lead = 4s
    gal11 = rows_by_key[("갈라디아서", "1", "1")]
    assert gal11["start_hms"] == "00:00:04"
    assert "?t=4" in gal11["video_url"]

    # 민수기 20:24 — known anomaly, no timestamp
    n2024 = rows_by_key[("민수기", "20", "24")]
    assert n2024["start_seconds"] == ""
    assert n2024["start_hms"] == ""
    assert n2024["video_url"].startswith("https://youtu.be/")
    # Chapter offset for 민수기 ch20 should be present; we don't know the exact value,
    # but it should be a multi-thousand-second offset (chapter 20 of a 3-hour book)
    assert "?t=" in n2024["video_url"]

    # No-op: counts include the 6 missing-audio rows
    assert counts["missing_audio"] == 6
