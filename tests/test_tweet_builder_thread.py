from datetime import date
from src.lib.models import ScheduleEntry
from src.lib.tweet_builder import build_thread, weighted_count

DEFAULT_TEMPLATE = "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"


def make_entry(text: str, ref: str = "시편 23:1-6") -> ScheduleEntry:
    return ScheduleEntry(
        date=date(2026, 1, 1), day_kind="regular", label="",
        bible_ref=ref, bible_text=text,
        youtube_url="https://youtu.be/abc",
    )


class TestBuildThread:
    def test_short_text_returns_single_tweet(self):
        e = make_entry("복 있는 사람은\n오만한 자리에 앉지 아니하고", ref="시편 1:1")
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=270)
        assert len(out) == 1
        assert "(1/" not in out[0]  # No numbering for single tweets

    def test_long_text_splits_at_newline(self):
        # Construct a text long enough to need 2-3 tweets, with verse boundaries
        verse1 = "여호와는 나의 목자시니 내가 부족함이 없으리로다"
        verse2 = "그가 나를 푸른 풀밭에 누이시며 쉴 만한 물 가로 인도하시는도다"
        verse3 = "내 영혼을 소생시키시고 자기 이름을 위하여 의의 길로 인도하시는도다"
        verse4 = "내가 사망의 음침한 골짜기로 다닐지라도 해를 두려워하지 않을 것은"
        verse5 = "주께서 나와 함께 하심이라 주의 지팡이와 막대기가 나를 안위하시나이다"
        text = "\n".join([verse1, verse2, verse3, verse4, verse5])
        e = make_entry(text)
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=120)  # Force splitting
        assert len(out) >= 2

    def test_each_thread_part_under_limit(self):
        long_text = "\n".join(["가나다라마바사아자차카타파하" * 5 for _ in range(6)])
        e = make_entry(long_text)
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=270)
        for part in out:
            assert weighted_count(part) <= 270

    def test_first_tweet_has_youtube_url(self):
        long_text = "\n".join([f"절 {i} " + "가" * 50 for i in range(5)])
        e = make_entry(long_text)
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=200)
        assert "https://youtu.be/abc" in out[0]
        # YouTube URL should NOT repeat in subsequent parts
        for part in out[1:]:
            assert "https://youtu.be/abc" not in part

    def test_thread_numbering_format(self):
        long_text = "\n".join([f"절 {i} " + "가" * 50 for i in range(5)])
        e = make_entry(long_text)
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=200)
        if len(out) > 1:
            assert "(1/" in out[0]
            assert f"({len(out)}/{len(out)})" in out[-1]

    def test_first_tweet_has_ref(self):
        long_text = "\n".join(["가" * 80 for _ in range(5)])
        e = make_entry(long_text, ref="시편 119:1-5")
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=200)
        assert "시편 119:1-5" in out[0]
