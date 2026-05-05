"""Tests for scripts.verify_videos."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import verify_videos as vv


def test_load_youtube_videos(tmp_path: Path):
    p = tmp_path / "yt.csv"
    p.write_text(
        "book,chapter,video_id,video_url,title\n"
        "유다서,0,jud,https://youtu.be/jud,유다서\n"
        "창세기,1,gen1,https://youtu.be/gen1,창세기 1장\n",
        encoding="utf-8",
    )
    rows = vv.load_youtube_videos(p)
    assert ("유다서", 0, "jud", "https://youtu.be/jud") in rows
    assert ("창세기", 1, "gen1", "https://youtu.be/gen1") in rows


def test_load_durations(tmp_path: Path):
    p = tmp_path / "dur.csv"
    p.write_text(
        "folder,subfolder1,subfolder2,filename,duration_sec\n"
        "tts_result-slow,갈,1,1.mp4,17.470\n"
        "tts_result-slow,갈,1,2.mp4,18.135\n"
        "tts_result-slow,갈,0,갈라디아서-1장.mp4,254.235\n",
        encoding="utf-8-sig",
    )
    verse, chap = vv.load_durations(p)
    assert verse[("갈", 1, 1)] == 17.470
    assert chap[("갈", 1)] == 254.235


def test_load_chapter_starts(tmp_path: Path):
    p = tmp_path / "starts.csv"
    p.write_text(
        "book,chapter,start_seconds\n"
        "갈라디아서,1,0.998\n"
        "갈라디아서,2,258.232\n",
        encoding="utf-8-sig",
    )
    cs = vv.load_chapter_starts(p)
    assert cs[("갈라디아서", 1)] == 0.998


def test_check_book_all_ok(tmp_path, monkeypatch):
    """Synthetic 2-chapter book with consistent durations passes all stages."""
    short = "갈"
    book = "갈라디아서"
    verse = {(short, 1, 1): 17.470, (short, 2, 1): 8.680}
    # chapter video = 3 + Σ verse
    chap = {(short, 1): 3.0 + 17.470, (short, 2): 3.0 + 8.680}
    # ch1 start ≈ 1s, ch2 start ≈ ch1 + audio_content + 6s gap
    starts = {(book, 1): 1.0, (book, 2): 1.0 + (chap[(short, 1)] - 3.0) + 7.0}
    # Set up local mp4 stubs by patching mp4_duration_seconds
    book_dur_expected = sum(chap.values()) + 2 * 3.0  # 56.285

    def fake_dur(p):
        if p.name == f"{book}.mp4":
            return book_dur_expected
        if p.name == "background2.mp4":
            return 3.0
        return 0.0

    monkeypatch.setattr(vv, "mp4_duration_seconds", fake_dur)
    monkeypatch.setattr(vv, "TTS_ROOT", tmp_path)
    (tmp_path / short).mkdir()
    (tmp_path / short / f"{book}.mp4").write_bytes(b"\x00")

    rep = vv.check_book(book, short, [(0, "vid", "https://y/vid")],
                       verse, chap, starts, fetch_youtube=False)
    assert rep.status == "OK", rep.notes
    assert rep.chapter_checks_ok == 2
    assert rep.chapter_checks_total == 2
    assert rep.silence_gaps_ok is True


def test_check_book_warns_when_chapter_composition_drifts(tmp_path, monkeypatch):
    short = "갈"
    book = "갈라디아서"
    verse = {(short, 1, 1): 17.470}
    # Inject a 0.5s drift inside ch1 (above 0.1s tolerance)
    chap = {(short, 1): 3.0 + 17.470 + 0.5}
    starts = {(book, 1): 1.0}
    book_dur = chap[(short, 1)] + 3.0

    def fake_dur(p):
        return book_dur if p.name == f"{book}.mp4" else (3.0 if p.name == "background2.mp4" else 0.0)

    monkeypatch.setattr(vv, "mp4_duration_seconds", fake_dur)
    monkeypatch.setattr(vv, "TTS_ROOT", tmp_path)
    (tmp_path / short).mkdir()
    (tmp_path / short / f"{book}.mp4").write_bytes(b"\x00")
    rep = vv.check_book(book, short, [(0, "vid", "")], verse, chap, starts, fetch_youtube=False)
    assert rep.status == "WARN"
    assert rep.chapter_checks_ok == 0


def test_check_book_whitelists_known_anomaly(tmp_path, monkeypatch):
    """민수기 ch20 composition drift is whitelisted (corrupt v24-29)."""
    short = "민"
    book = "민수기"
    verse = {(short, 20, 23): 9.258}  # only one tracked verse, large drift expected
    chap = {(short, 20): 50.0}  # chapter dur intentionally inconsistent
    starts = {(book, 20): 1.0}

    def fake_dur(p):
        return 56.0 if p.name == f"{book}.mp4" else 3.0

    monkeypatch.setattr(vv, "mp4_duration_seconds", fake_dur)
    monkeypatch.setattr(vv, "TTS_ROOT", tmp_path)
    (tmp_path / short).mkdir()
    (tmp_path / short / f"{book}.mp4").write_bytes(b"\x00")
    rep = vv.check_book(book, short, [(0, "vid", "")], verse, chap, starts, fetch_youtube=False)
    assert rep.chapter_checks_ok == 1  # whitelisted as OK
    # status may still be WARN/FAIL on book-composition stage; verify the whitelist path
    assert any("whitelisted" in n for n in rep.notes)


def test_check_book_fails_when_book_mp4_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(vv, "TTS_ROOT", tmp_path)
    rep = vv.check_book("갈라디아서", "갈", [], {}, {}, {}, fetch_youtube=False)
    assert rep.status == "FAIL"
    assert "book mp4 missing" in rep.notes


def test_render_report_includes_summary():
    r1 = vv.BookReport(book="A", status="OK")
    r2 = vv.BookReport(book="B", status="WARN")
    r3 = vv.BookReport(book="C", status="FAIL")
    out = vv.render_report([r1, r2, r3])
    assert "| A |" in out
    assert "1 OK, 1 WARN, 1 FAIL" in out


REAL_YT = Path("data/youtube_videos.csv")
REAL_DUR = Path("temp/mp4_durations.csv")
REAL_STARTS = Path("temp/book_chapter_starts.csv")
REAL_TTS = Path("temp/tts_result-slow")


@pytest.mark.skipif(
    not all(p.exists() for p in [REAL_YT, REAL_DUR, REAL_STARTS, REAL_TTS]),
    reason="real corpus files not present",
)
def test_run_offline_passes_for_known_books():
    """End-to-end offline run on real corpus should not exit with FAIL."""
    rc = vv.run(fetch_youtube=False, books_filter=["갈라디아서", "마태복음", "시편"])
    assert rc == 0
