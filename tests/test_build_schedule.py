from scripts.build_schedule import (
    BibleTextLookup,
    YoutubeUrlLookup,
    pick_first_n_verses,
    resolve_ref_text,
)


class TestPickFirstNVerses:
    def test_picks_first_three(self):
        lookup = BibleTextLookup({
            ("시편", 1, 1): "복 있는 사람은 악인의 꾀를 따르지 아니하며",
            ("시편", 1, 2): "오직 여호와의 율법을 즐거워하여",
            ("시편", 1, 3): "그는 시냇가에 심은 나무가 철을 따라 열매를 맺으며",
            ("시편", 1, 4): "악인들은 그렇지 아니함이여",
        })
        ref, text, url = pick_first_n_verses(lookup, "시편", 1, n=3)
        assert ref == "시편 1:1-3"
        assert "복 있는 사람은" in text
        assert "악인들은 그렇지 아니함이여" not in text
        assert url == ""  # no URL data

    def test_chapter_with_only_one_verse(self):
        lookup = BibleTextLookup({("창세기", 1, 1): "태초에 하나님이 천지를 창조하시니라"})
        ref, text, url = pick_first_n_verses(lookup, "창세기", 1, n=3)
        assert ref == "창세기 1:1"
        assert "태초에" in text

    def test_returns_first_verse_url(self):
        lookup = BibleTextLookup(
            {("시편", 1, v): f"v{v}" for v in range(1, 4)},
            url_data={
                ("시편", 1, 1): "https://youtu.be/x?t=1",
                ("시편", 1, 2): "https://youtu.be/x?t=10",
                ("시편", 1, 3): "https://youtu.be/x?t=20",
            },
        )
        ref, text, url = pick_first_n_verses(lookup, "시편", 1, n=3)
        assert url == "https://youtu.be/x?t=1"


class TestResolveRefText:
    def test_explicit_range(self):
        lookup = BibleTextLookup({
            ("빌립보서", 3, 13): "형제들아 나는 아직",
            ("빌립보서", 3, 14): "푯대를 향하여 좇아가노라",
        })
        ref, text, url = resolve_ref_text(lookup, "빌립보서 3:13-14")
        assert "13" in ref and "14" in ref
        assert "형제들아" in text and "푯대" in text

    def test_single_verse_with_url(self):
        lookup = BibleTextLookup(
            {("요한복음", 3, 16): "하나님이 세상을 이처럼 사랑하사"},
            url_data={("요한복음", 3, 16): "https://youtu.be/john?t=300"},
        )
        ref, text, url = resolve_ref_text(lookup, "요한복음 3:16")
        assert "16" in ref
        assert "하나님이" in text
        assert url == "https://youtu.be/john?t=300"

    def test_range_returns_first_verse_url(self):
        lookup = BibleTextLookup(
            {("로마서", 8, v): f"v{v}" for v in (28, 29, 30)},
            url_data={
                ("로마서", 8, 28): "https://youtu.be/r?t=100",
                ("로마서", 8, 29): "https://youtu.be/r?t=110",
            },
        )
        ref, text, url = resolve_ref_text(lookup, "로마서 8:28-30")
        assert url == "https://youtu.be/r?t=100"

    def test_whole_chapter_picks_first_3(self):
        lookup = BibleTextLookup({("시편", 1, v): f"v{v}" for v in range(1, 6)})
        ref, text, url = resolve_ref_text(lookup, "시편 1")
        assert ref == "시편 1:1-3"

    def test_unparseable_returns_input(self):
        lookup = BibleTextLookup({})
        ref, text, url = resolve_ref_text(lookup, "garbage string")
        assert ref == "garbage string"
        assert text == ""
        assert url == ""


class TestYoutubeUrlLookup:
    def test_finds_url(self):
        lookup = YoutubeUrlLookup({("시편", 1): "https://youtu.be/abc"})
        assert lookup.get("시편", 1) == "https://youtu.be/abc"

    def test_missing_returns_empty(self):
        lookup = YoutubeUrlLookup({})
        assert lookup.get("시편", 999) == ""

    def test_falls_back_to_whole_book_url(self):
        lookup = YoutubeUrlLookup({("시편", 0): "https://youtu.be/wholebook"})
        assert lookup.get("시편", 5) == "https://youtu.be/wholebook"
        assert lookup.get("시편", 150) == "https://youtu.be/wholebook"

    def test_chapter_url_takes_precedence_over_book(self):
        lookup = YoutubeUrlLookup({
            ("창세기", 0): "https://youtu.be/wholebook",
            ("창세기", 1): "https://youtu.be/chapter1",
        })
        assert lookup.get("창세기", 1) == "https://youtu.be/chapter1"
        assert lookup.get("창세기", 5) == "https://youtu.be/wholebook"

    def test_missing_book_entirely_returns_empty(self):
        lookup = YoutubeUrlLookup({("시편", 0): "x"})
        assert lookup.get("계시록", 1) == ""
