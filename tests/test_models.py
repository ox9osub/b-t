from datetime import date, datetime
import pytest
from src.lib.models import ScheduleEntry, BibleRef


class TestBibleRef:
    def test_single_verse(self):
        ref = BibleRef.parse("창세기 1:1")
        assert ref.book == "창세기"
        assert ref.chapter == 1
        assert ref.verse_start == 1
        assert ref.verse_end == 1

    def test_verse_range(self):
        ref = BibleRef.parse("시편 23:1-3")
        assert ref.book == "시편"
        assert ref.chapter == 23
        assert ref.verse_start == 1
        assert ref.verse_end == 3

    def test_whole_chapter(self):
        ref = BibleRef.parse("잠언 1")
        assert ref.book == "잠언"
        assert ref.chapter == 1
        assert ref.verse_start is None
        assert ref.verse_end is None

    def test_two_digit_chapter_and_verse(self):
        ref = BibleRef.parse("요한복음 14:15-21")
        assert ref.book == "요한복음"
        assert ref.chapter == 14
        assert ref.verse_start == 15
        assert ref.verse_end == 21

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            BibleRef.parse("not a reference")

    def test_format_back_to_string(self):
        ref = BibleRef.parse("시편 23:1-3")
        assert ref.format() == "시편 23:1-3"

    def test_format_single_verse(self):
        ref = BibleRef.parse("창세기 1:1")
        assert ref.format() == "창세기 1:1"

    def test_format_whole_chapter(self):
        ref = BibleRef.parse("잠언 1")
        assert ref.format() == "잠언 1"


class TestScheduleEntry:
    def test_create_minimal(self):
        e = ScheduleEntry(
            date=date(2026, 1, 1),
            day_kind="meaningful",
            label="새해 새 마음",
            bible_ref="빌립보서 3:13-14",
            bible_text="형제들아 나는 아직 내가 잡은 줄로 여기지 아니하고...",
            youtube_url="https://youtu.be/abc123",
        )
        assert e.date == date(2026, 1, 1)
        assert e.day_kind == "meaningful"
        assert e.tweet_id is None
        assert e.posted_at is None

    def test_already_posted(self):
        e = ScheduleEntry(
            date=date(2026, 1, 1), day_kind="regular",
            label="", bible_ref="시편 1:1", bible_text="복 있는 사람은",
            youtube_url="https://youtu.be/x",
            tweet_id="1234567890",
            posted_at=datetime(2026, 1, 1, 21, 5, 0),
        )
        assert e.already_posted() is True

    def test_not_posted_yet(self):
        e = ScheduleEntry(
            date=date(2026, 1, 1), day_kind="regular",
            label="", bible_ref="시편 1:1", bible_text="복 있는 사람은",
            youtube_url="https://youtu.be/x",
        )
        assert e.already_posted() is False
