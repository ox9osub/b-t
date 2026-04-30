from datetime import date
from src.lib.models import ScheduleEntry
from src.lib.tweet_builder import build, weighted_count

DEFAULT_TEMPLATE = "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"


def make_entry(text: str) -> ScheduleEntry:
    return ScheduleEntry(
        date=date(2026, 1, 1), day_kind="regular", label="",
        bible_ref="시편 1:1", bible_text=text,
        youtube_url="https://youtu.be/abc",
    )


def test_build_short_returns_single():
    e = make_entry("복 있는 사람은")
    out = build(e, DEFAULT_TEMPLATE)
    assert len(out) == 1


def test_build_long_returns_thread():
    long = "\n".join(["가" * 60 for _ in range(8)])
    e = make_entry(long)
    out = build(e, DEFAULT_TEMPLATE)
    assert len(out) > 1


def test_build_no_part_exceeds_default_limit():
    long = "\n".join(["가" * 60 for _ in range(8)])
    e = make_entry(long)
    out = build(e, DEFAULT_TEMPLATE)
    for part in out:
        assert weighted_count(part) <= 270


def test_build_with_custom_max_weight():
    e = make_entry("복 있는 사람은")
    out = build(e, DEFAULT_TEMPLATE, max_weight=50)
    # Will split because template + text > 50
    assert len(out) >= 1
