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

    def test_template_with_hashtags_counted_in_overhead(self):
        """템플릿에 해시태그가 있으면 overhead 계산에 포함되어 budget이 줄어들어야 함."""
        template = (
            "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"
            "\n\n#오늘의말씀 #말씀묵상 #성경듣기"
        )
        # bible_text 단독은 270 budget에 맞지만, 해시태그까지 합치면 단일 트윗 초과 케이스
        text = "가" * 100  # weight 200
        e = make_entry(text, ref="시편 1:1")
        out = build_thread(e, template, max_weight=270)
        # 단일이면 weight 200 + overhead(~57) + hashtag(33) = ~290 초과 → 스레드여야 함
        assert len(out) >= 2, (
            f"expected thread for 200-weight text with hashtag template, got {len(out)} parts:\n"
            + "\n---\n".join(out)
        )
        for i, part in enumerate(out):
            assert weighted_count(part) <= 270, (
                f"part {i+1} weight={weighted_count(part)} > 270:\n{part}"
            )

    def test_regression_2026_05_16_timothy(self):
        """2026-05-16 디모데후서 3:14-15: 본문 200 weight + 해시태그 템플릿에서
        단일이 283 weight인데 chunks=1 fallback 버그로 over-limit 단일이 리턴된 케이스."""
        bible_text = (
            "그러나 너는 배우고 확신한 일에 거하라 네가 뉘게서 배운 것을 알며\n"
            "또 네가 어려서부터 성경을 알았나니 성경은 능히 너로 하여금 그리스도 "
            "예수 안에 있는 믿음으로 말미암아 구원에 이르는 지혜가 있게 하느니라"
        )
        template = (
            "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"
            "\n\n#오늘의말씀 #말씀묵상 #성경듣기"
        )
        e = ScheduleEntry(
            date=date(2026, 5, 16), day_kind="regular", label="",
            bible_ref="디모데후서 3:14-15", bible_text=bible_text,
            youtube_url="https://youtu.be/ai40tkeZ4gw?t=653",
        )
        out = build_thread(e, template, max_weight=270)
        assert len(out) >= 2, f"expected thread, got {len(out)} parts"
        for i, part in enumerate(out):
            assert weighted_count(part) <= 270, (
                f"part {i+1} weight={weighted_count(part)} > 270:\n{part}"
            )
        # 첫 트윗에 해시태그 보존되어야 함 (스레드 모드에서 템플릿 사용)
        assert "#오늘의말씀" in out[0]
        # 첫 트윗에 ref와 URL 포함
        assert "디모데후서 3:14-15" in out[0]
        assert "https://youtu.be/ai40tkeZ4gw?t=653" in out[0]

    def test_force_split_no_delimiters(self):
        """공백·줄바꿈·문장부호 없는 긴 텍스트도 over-limit 안 나오게 강제 분할."""
        text = "가" * 200  # weight 400, no delimiters
        template = "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"
        e = make_entry(text, ref="시편 1:1")
        out = build_thread(e, template, max_weight=270)
        assert len(out) >= 2
        for part in out:
            assert weighted_count(part) <= 270

    def test_extreme_low_max_weight_doesnt_crash(self):
        """When max_weight is so low that template overhead alone exceeds it,
        _budget_for_text falls back to the 50-weight floor.  Verify we still
        produce something usable (not crashing, not infinite loop)."""
        # ref + URL + suffix overhead is ~50 weight already; 60 max forces budget floor
        long_text = "\n".join(["가" * 100 for _ in range(3)])
        e = make_entry(long_text, ref="시편 119:1-3")
        out = build_thread(e, DEFAULT_TEMPLATE, max_weight=60)
        # Should produce at least one part (may exceed 60 but not crash)
        assert len(out) >= 1
        # First tweet must contain the URL even if it overflows
        assert "https://youtu.be/abc" in out[0]
