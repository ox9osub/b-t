from scripts.build_schedule import (
    BibleTextLookup,
    YoutubeUrlLookup,
    ScheduleBuilder,
)


def _bible_with(*entries):
    return BibleTextLookup({(b, c, v): t for b, c, v, t in entries})


class TestScheduleBuilderFromYearPlan:
    def test_builds_all_rows(self):
        bible = _bible_with(
            ("빌립보서", 3, 13, "형제들아 나는 아직"),
            ("빌립보서", 3, 14, "푯대를 향하여 좇아가노라"),
            ("시편", 1, 1, "복 있는 사람은"),
            ("시편", 1, 2, "오직 여호와의 율법을"),
            ("시편", 1, 3, "그는 시냇가에 심은"),
        )
        yt = YoutubeUrlLookup({
            ("빌립보서", 0): "https://youtu.be/phil",
            ("시편", 0): "https://youtu.be/psalms",
        })
        plan = [
            {"date": "2026-01-01", "day_kind": "meaningful", "label": "신년",
             "bible_ref": "빌립보서 3:13-14", "note": ""},
            {"date": "2026-01-02", "day_kind": "regular", "label": "",
             "bible_ref": "시편 1:1-3", "note": ""},
        ]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n— {bible_ref}\n🎧 {youtube_url}")
        rows = builder.build_from_year_plan(plan)

        assert len(rows) == 2
        assert rows[0]["day_kind"] == "meaningful"
        assert rows[0]["label"] == "신년"
        assert "형제들아" in rows[0]["bible_text"]
        assert rows[0]["youtube_url"] == "https://youtu.be/phil"
        assert rows[1]["day_kind"] == "regular"
        assert "복 있는" in rows[1]["bible_text"]
        assert builder.summary["meaningful"] == 1
        assert builder.summary["regular"] == 1
        assert builder.summary["total"] == 2

    def test_youtube_fallback_to_whole_book(self):
        # No verse URL, no chapter URL — falls back to book-level
        bible = _bible_with(("요한복음", 3, 16, "하나님이 세상을 이처럼 사랑하사"))
        yt = YoutubeUrlLookup({("요한복음", 0): "https://youtu.be/john"})
        plan = [{"date": "2026-02-01", "day_kind": "regular", "label": "",
                 "bible_ref": "요한복음 3:16", "note": ""}]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n🎧 {youtube_url}")
        rows = builder.build_from_year_plan(plan)
        assert rows[0]["youtube_url"] == "https://youtu.be/john"
        assert builder.summary["missing_youtube"] == []

    def test_per_verse_url_preferred_over_book_url(self):
        bible = BibleTextLookup(
            {("요한복음", 3, 16): "하나님이 세상을 이처럼 사랑하사"},
            url_data={("요한복음", 3, 16): "https://youtu.be/john?t=300"},
        )
        yt = YoutubeUrlLookup({("요한복음", 0): "https://youtu.be/john"})
        plan = [{"date": "2026-02-01", "day_kind": "regular", "label": "",
                 "bible_ref": "요한복음 3:16", "note": ""}]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n🎧 {youtube_url}")
        rows = builder.build_from_year_plan(plan)
        assert rows[0]["youtube_url"] == "https://youtu.be/john?t=300"

    def test_missing_youtube_recorded(self):
        bible = _bible_with(("시편", 1, 1, "복 있는 사람은"))
        yt = YoutubeUrlLookup({})
        plan = [{"date": "2026-01-01", "day_kind": "regular", "label": "",
                 "bible_ref": "시편 1:1", "note": ""}]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n🎧 {youtube_url}")
        builder.build_from_year_plan(plan)
        assert builder.summary["missing_youtube"]

    def test_missing_text_recorded(self):
        bible = BibleTextLookup({})
        yt = YoutubeUrlLookup({("시편", 0): "x"})
        plan = [{"date": "2026-01-01", "day_kind": "regular", "label": "",
                 "bible_ref": "시편 1:1", "note": ""}]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n🎧 {youtube_url}")
        builder.build_from_year_plan(plan)
        assert builder.summary["missing_text"]

    def test_long_text_marked_needs_thread(self):
        long_text = "가" * 200  # 200 Korean chars = 400 weight
        bible = _bible_with(("시편", 1, 1, long_text))
        yt = YoutubeUrlLookup({("시편", 0): "https://youtu.be/p"})
        plan = [{"date": "2026-01-01", "day_kind": "regular", "label": "",
                 "bible_ref": "시편 1:1", "note": ""}]
        builder = ScheduleBuilder(bible, yt, template="{bible_text}\n🎧 {youtube_url}")
        rows = builder.build_from_year_plan(plan)
        assert rows[0]["needs_thread"] == "TRUE"
        assert rows[0]["char_count"] > 280
