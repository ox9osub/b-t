from datetime import date
from scripts.build_schedule import (
    match_meaningful_day,
    pick_first_n_verses,
    BibleTextLookup,
    YoutubeUrlLookup,
    ScheduleBuilder,
)


class TestMatchMeaningfulDay:
    def test_matches_pattern(self):
        days = [{"pattern": "01-01", "name": "새해 새 마음",
                 "suggested_refs": "빌3:13-14, 사43:18-19"}]
        result = match_meaningful_day(date(2026, 1, 1), days)
        assert result is not None
        assert result["name"] == "새해 새 마음"

    def test_no_match(self):
        days = [{"pattern": "01-01", "name": "x", "suggested_refs": ""}]
        assert match_meaningful_day(date(2026, 6, 15), days) is None


class TestPickFirstNVerses:
    def test_picks_first_three(self):
        # 시뮬레이션 본문 lookup
        lookup = BibleTextLookup({
            ("시편", 1, 1): "복 있는 사람은 악인의 꾀를 따르지 아니하며",
            ("시편", 1, 2): "오직 여호와의 율법을 즐거워하여",
            ("시편", 1, 3): "그는 시냇가에 심은 나무가 철을 따라 열매를 맺으며",
            ("시편", 1, 4): "악인들은 그렇지 아니함이여",
        })
        ref, text = pick_first_n_verses(lookup, "시편", 1, n=3)
        assert ref == "시편 1:1-3"
        assert "복 있는 사람은" in text
        assert "시냇가에 심은 나무" in text
        assert "악인들은 그렇지 아니함이여" not in text

    def test_chapter_with_only_one_verse(self):
        lookup = BibleTextLookup({("창세기", 1, 1): "태초에 하나님이 천지를 창조하시니라"})
        ref, text = pick_first_n_verses(lookup, "창세기", 1, n=3)
        assert ref == "창세기 1:1"


class TestYoutubeUrlLookup:
    def test_finds_url(self):
        lookup = YoutubeUrlLookup({("시편", 1): "https://youtu.be/abc"})
        assert lookup.get("시편", 1) == "https://youtu.be/abc"

    def test_missing_returns_empty(self):
        lookup = YoutubeUrlLookup({})
        assert lookup.get("시편", 999) == ""

    def test_falls_back_to_whole_book_url(self):
        # When chapter URL is missing, return (book, 0) whole-book URL
        lookup = YoutubeUrlLookup({("시편", 0): "https://youtu.be/wholebook"})
        assert lookup.get("시편", 5) == "https://youtu.be/wholebook"
        assert lookup.get("시편", 150) == "https://youtu.be/wholebook"

    def test_chapter_url_takes_precedence_over_book(self):
        # If both chapter-specific and whole-book exist, use chapter
        lookup = YoutubeUrlLookup({
            ("창세기", 0): "https://youtu.be/wholebook",
            ("창세기", 1): "https://youtu.be/chapter1",
        })
        assert lookup.get("창세기", 1) == "https://youtu.be/chapter1"
        # But chapter 5 (no specific) falls back to whole-book
        assert lookup.get("창세기", 5) == "https://youtu.be/wholebook"

    def test_missing_book_entirely_returns_empty(self):
        lookup = YoutubeUrlLookup({("시편", 0): "x"})
        assert lookup.get("계시록", 1) == ""

    def test_has_any(self):
        lookup = YoutubeUrlLookup({("시편", 0): "x", ("창세기", 1): "y"})
        assert lookup.has_any("시편") is True
        assert lookup.has_any("창세기") is True
        assert lookup.has_any("계시록") is False


class TestScheduleBuilder:
    def test_builds_full_year(self):
        bible = BibleTextLookup({
            ("시편", ch, v): f"시편 {ch}편 {v}절 본문"
            for ch in range(1, 151) for v in range(1, 4)
        })
        for ch in range(1, 32):
            for v in range(1, 4):
                bible._data[("잠언", ch, v)] = f"잠언 {ch}장 {v}절 본문"
        bible._data[("빌립보서", 3, 13)] = "형제들아 나는 아직"
        bible._data[("빌립보서", 3, 14)] = "푯대를 향하여 좇아가노라"

        yt = YoutubeUrlLookup({
            ("시편", ch): f"https://youtu.be/psalm{ch}" for ch in range(1, 151)
        })
        for ch in range(1, 32):
            yt._data[("잠언", ch)] = f"https://youtu.be/prov{ch}"
        yt._data[("빌립보서", 3)] = "https://youtu.be/phil3"

        meaningful = [{"pattern": "01-01", "name": "새해 새 마음",
                       "suggested_refs": "빌립보서 3:13-14"}]

        builder = ScheduleBuilder(bible, yt, meaningful, template="{bible_text}\n— {bible_ref}\n🎧 {youtube_url}")
        rows = builder.build_year(2026)

        assert len(rows) == 365
        # First day = meaningful
        assert rows[0]["day_kind"] == "meaningful"
        assert rows[0]["label"] == "새해 새 마음"
        assert rows[0]["bible_ref"] == "빌립보서 3:13-14"
        # Day 2 = regular, should be 시편 1
        assert rows[1]["day_kind"] == "regular"
        assert "시편 1" in rows[1]["bible_ref"]


class TestScheduleBuilderReportsErrors:
    def test_missing_youtube_url_recorded_in_summary(self):
        bible = BibleTextLookup({("시편", 1, 1): "복 있는 사람은"})
        yt = YoutubeUrlLookup({})  # No URLs
        builder = ScheduleBuilder(bible, yt, meaningful_days=[],
                                   template="{bible_text}\n🎧 {youtube_url}")
        rows = builder.build_year(2026)
        assert builder.summary["missing_youtube"]

    def test_book_level_url_satisfies_chapter_lookup(self):
        # 시편 has only whole-book audio (chapter=0); chapter-specific lookups
        # should fall back and NOT register as missing.
        bible = BibleTextLookup({("시편", ch, v): f"v{v}" for ch in range(1, 151) for v in range(1, 4)})
        for ch in range(1, 32):
            for v in range(1, 4):
                bible._data[("잠언", ch, v)] = f"v{v}"
        yt = YoutubeUrlLookup({
            ("시편", 0): "https://youtu.be/psalms-whole",
            ("잠언", 0): "https://youtu.be/proverbs-whole",
        })
        builder = ScheduleBuilder(bible, yt, meaningful_days=[],
                                   template="{bible_text}\n🎧 {youtube_url}")
        rows = builder.build_year(2026)
        # No missing youtube — fallback worked
        assert builder.summary["missing_youtube"] == []
        # All rows have a URL
        for r in rows:
            assert r["youtube_url"].startswith("https://")
