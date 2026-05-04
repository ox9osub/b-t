from scripts.crawl_youtube import parse_title


def test_parse_basic_title():
    book, chapter = parse_title("창세기 1장")
    assert book == "창세기"
    assert chapter == 1


def test_parse_two_digit_chapter():
    book, chapter = parse_title("시편 119장")
    assert book == "시편"
    assert chapter == 119


def test_parse_with_extra_suffix():
    # Titles may have extras like "낭독", date, etc.
    book, chapter = parse_title("출애굽기 5장 낭독 - 2024년")
    assert book == "출애굽기"
    assert chapter == 5


def test_parse_no_match_returns_none():
    assert parse_title("This is not a Bible chapter") is None
    assert parse_title("Episode 1") is None


def test_parse_book_with_number_prefix():
    # Books like "사무엘상", "디모데후서" — Korean uses 상/하/전/후 suffix
    book, chapter = parse_title("사무엘상 3장")
    assert book == "사무엘상"
    assert chapter == 3


def test_parse_whole_book_single_video():
    # Whole-book single-video uploads: chapter=0 sentinel
    book, chapter = parse_title("요한계시록 [오디오 성경, 데이터 70~90% 절약]")
    assert book == "요한계시록"
    assert chapter == 0


def test_parse_whole_book_no_audio_marker_returns_none():
    # Bracketed titles without "[오디오" marker should not be treated as whole-book
    assert parse_title("Trailer [2024]") is None


def test_parse_whole_book_with_digit_in_name():
    # Books like 요한1서/2서/3서 contain digits in the name
    book, chapter = parse_title("요한1서 [오디오 성경, 데이터 70~90% 절약]")
    assert book == "요한1서"
    assert chapter == 0
