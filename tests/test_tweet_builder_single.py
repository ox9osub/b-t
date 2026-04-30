from datetime import date
from src.lib.models import ScheduleEntry
from src.lib.tweet_builder import build_single, render_template

DEFAULT_TEMPLATE = "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"


def make_entry(text: str = "복 있는 사람은", ref: str = "시편 1:1",
               url: str = "https://youtu.be/abc") -> ScheduleEntry:
    return ScheduleEntry(
        date=date(2026, 1, 1), day_kind="regular", label="",
        bible_ref=ref, bible_text=text, youtube_url=url,
    )


class TestRenderTemplate:
    def test_basic_substitution(self):
        e = make_entry()
        out = render_template(DEFAULT_TEMPLATE, e)
        assert "복 있는 사람은" in out
        assert "— 시편 1:1" in out
        assert "https://youtu.be/abc" in out

    def test_literal_backslash_n_converted(self):
        # Sheets cell may contain literal '\n' (two chars) → must convert
        tmpl = "{bible_text}\\n\\n— {bible_ref}"
        e = make_entry()
        out = render_template(tmpl, e)
        assert "\n\n" in out

    def test_real_newlines_preserved(self):
        # If actually-newlines are in template, they stay
        tmpl = "{bible_text}\n— {bible_ref}"
        e = make_entry()
        out = render_template(tmpl, e)
        assert "\n" in out


class TestBuildSingle:
    def test_returns_one_string(self):
        e = make_entry()
        out = build_single(e, DEFAULT_TEMPLATE)
        assert isinstance(out, str)
        assert "시편 1:1" in out
