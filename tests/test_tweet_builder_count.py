from src.lib.tweet_builder import weighted_count


class TestWeightedCount:
    def test_empty_string(self):
        assert weighted_count("") == 0

    def test_ascii_each_one_weight(self):
        assert weighted_count("hello") == 5
        assert weighted_count("hello world") == 11

    def test_korean_each_two_weight(self):
        # 5 Hangul characters × 2 weight = 10
        assert weighted_count("안녕하세요") == 10

    def test_mixed_korean_ascii(self):
        # "Hi 안녕": 'H'(1) + 'i'(1) + ' '(1) + '안'(2) + '녕'(2) = 7
        assert weighted_count("Hi 안녕") == 7

    def test_url_counts_as_23(self):
        # Any URL counts as exactly 23, regardless of actual length
        short = "https://x.co/a"
        long = "https://www.example.com/very/long/path/with/many/segments?and=query&params=here"
        assert weighted_count(short) == 23
        assert weighted_count(long) == 23

    def test_url_in_korean_text(self):
        # "보세요 https://youtu.be/abc": 보(2)+세(2)+요(2)+space(1)+URL(23) = 30
        assert weighted_count("보세요 https://youtu.be/abc") == 30

    def test_emoji_counts_as_two(self):
        # 🎧 = 2 weight (CJK weight rule applies to emoji per twitter-text)
        assert weighted_count("🎧") == 2

    def test_newline_counts_as_one(self):
        assert weighted_count("a\nb") == 3

    def test_multiple_urls(self):
        # Two URLs = 46, plus space = 47
        assert weighted_count("https://a.io https://b.io") == 47

    def test_psalm_example(self):
        # spec section 6.1 example
        text = (
            "복 있는 사람은 악인들의 꾀를 따르지 아니하며\n"
            "죄인들의 길에 서지 아니하며\n"
            "오만한 자들의 자리에 앉지 아니하고\n\n"
            "— 시편 1:1\n\n"
            "🎧 https://youtu.be/abc123"
        )
        # Just verify it's well under 280
        assert weighted_count(text) < 280
        # And reasonably close to expected ~150-180 weight
        assert weighted_count(text) > 100
