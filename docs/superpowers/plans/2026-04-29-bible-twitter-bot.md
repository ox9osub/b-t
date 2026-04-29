# Bible Twitter Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 KST 06:00에 트위터로 성경 본문 + YouTube 낭독 링크를 자동 발행하는 봇을 구축한다 (의미있는 날 큐레이션 + 평일 시편/잠언 순환).

**Architecture:** Python 3.11+ 기반. 1회성 준비 스크립트(`crawl_youtube`, `build_schedule`)로 Google Sheet에 1년치 일정을 채워두고, 매일 GitHub Actions cron이 `post_today.py`를 실행해 오늘 행을 읽어 트위터에 발행. 멱등성은 `tweet_id` 컬럼으로 보장. 280 weight 초과 본문은 절 경계로 자동 스레드 분할.

**Tech Stack:** Python 3.11+, tweepy (Twitter API v2), gspread (Google Sheets), yt-dlp (YouTube 크롤링), pytest (테스트), GitHub Actions (cron 실행).

**Spec:** `docs/superpowers/specs/2026-04-29-bible-twitter-bot-design.md`

---

## Task 1: 외부 계정 셋업 가이드 (사용자가 비동기로 진행)

**목적**: X Developer 승인은 시간 걸림 (즉시~며칠). 코드 작업과 병행하도록 가이드 문서부터 만든다.

**Files:**
- Create: `docs/setup/01-x-developer-account.md`
- Create: `docs/setup/02-google-cloud-service-account.md`
- Create: `docs/setup/README.md`

- [ ] **Step 1: Create `docs/setup/README.md`**

```markdown
# 외부 서비스 셋업 가이드

이 봇은 외부 서비스 3개의 계정/인증이 필요합니다. 시간이 오래 걸리는 것부터 시작하세요.

## 셋업 순서 (병렬 가능)

1. [X (Twitter) Developer 계정](./01-x-developer-account.md) — **가장 먼저 시작**. 승인 대기 시간 발생 가능 (즉시~며칠)
2. [Google Cloud Service Account](./02-google-cloud-service-account.md) — 30분 정도 소요
3. YouTube 채널 — 본인 채널 URL만 메모해두면 됨 (계정 신청 불필요)

각 단계 완료 후 받은 자격증명은 **GitHub Secrets**에 저장합니다 (Step 5의 `daily-post.yml` 참조).
```

- [ ] **Step 2: Create `docs/setup/01-x-developer-account.md`**

```markdown
# X (Twitter) Developer 계정 셋업

## 1. 신청
1. https://developer.x.com/ 접속 → "Sign up for Free Account"
2. 사용처 설명 (영어): 예시 — "Personal devotional bot for posting daily Bible verses with audio links to my own Twitter account."
3. 약관 동의 → 신청

## 2. App 생성
1. 승인 후 Developer Portal → "Projects & Apps" → "Add App"
2. App 이름 (예: `bible-bot`)
3. **App permissions** → "Read and write" 로 변경 (기본 Read만은 트윗 발행 불가)

## 3. 자격증명 4개 발급
"Keys and tokens" 탭에서 다음을 발급/복사:

| 이름 | GitHub Secret 이름 |
|---|---|
| API Key | `TWITTER_API_KEY` |
| API Secret | `TWITTER_API_SECRET` |
| Access Token | `TWITTER_ACCESS_TOKEN` |
| Access Token Secret | `TWITTER_ACCESS_SECRET` |

⚠️ **주의**: Access Token은 App permissions 변경 후 **재생성**해야 write 권한이 적용됩니다.

## 4. Free 등급 한도 확인
- 월 500건 쓰기 (이 봇은 월 30~50건 발행하므로 충분)
- 일 16건까지

## 5. 검증
이 자격증명으로 실제 발행이 되는지는 Task 8에서 확인합니다.
```

- [ ] **Step 3: Create `docs/setup/02-google-cloud-service-account.md`**

```markdown
# Google Cloud Service Account 셋업

Google Sheets를 코드에서 자동으로 읽고 쓰기 위해 Service Account가 필요합니다.

## 1. Google Cloud 프로젝트 생성
1. https://console.cloud.google.com/ 접속
2. 상단 프로젝트 선택 → "New Project" → 이름: `bible-bot` (예시)

## 2. Sheets API 활성화
1. "APIs & Services" → "Library"
2. "Google Sheets API" 검색 → "Enable"
3. "Google Drive API" 도 동일하게 Enable (시트 접근에 필요)

## 3. Service Account 생성
1. "APIs & Services" → "Credentials" → "Create credentials" → "Service account"
2. 이름: `bible-bot-runner` → "Create and continue"
3. Role: 비워두고 "Done"

## 4. JSON 키 발급
1. 방금 만든 Service Account 클릭 → "Keys" 탭 → "Add Key" → "Create new key" → JSON
2. 자동 다운로드되는 JSON 파일 저장 (예: `bible-bot-creds.json`)
3. **GitHub Secret 이름**: `GOOGLE_SHEETS_CREDS` (JSON 전체 내용을 복붙)

## 5. Google Sheet 생성 + 공유
1. https://sheets.google.com → 새 스프레드시트 생성 → 이름 `bible-bot-schedule`
2. URL에서 Sheet ID 복사 (예: `https://docs.google.com/spreadsheets/d/`**`1AbCdEf...`**`/edit`)
3. **GitHub Secret 이름**: `GOOGLE_SHEET_ID`
4. 시트 우상단 "Share" → Service Account 이메일(JSON의 `client_email` 필드)을 **편집자**로 추가

## 6. 시트 탭 만들기
다음 3개 탭을 만들어주세요 (탭 이름이 정확해야 함):
- `schedule`
- `meaningful_days`
- `config`

각 탭의 헤더와 초기값은 Task 13에서 자동으로 채워집니다.
```

- [ ] **Step 4: Commit**

```bash
git add docs/setup/
git commit -m "docs: external service setup guides"
```

---

## Task 2: 프로젝트 스캐폴딩 + Git 초기화

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `README.md` (덮어쓰기)
- Create: `src/__init__.py`
- Create: `src/lib/__init__.py`
- Create: `tests/__init__.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: Initialize git repo**

Run:
```bash
cd "c:/Users/suble/Desktop/work/project/b-t" && git init -b main
```
Expected: `Initialized empty Git repository`

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.pytest_cache/
.venv/
venv/

# IDE
.vscode/
.idea/

# Secrets (must never be committed)
*.json.creds
bible-bot-creds.json
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Local data (potentially copyrighted Bible text)
data/bible_text.csv
data/youtube_videos.csv
```

- [ ] **Step 3: Create `requirements.txt`** (런타임 의존성)

```
tweepy>=4.14.0
gspread>=6.0.0
google-auth>=2.27.0
python-dateutil>=2.8.2
```

- [ ] **Step 4: Create `requirements-dev.txt`** (개발/테스트용)

```
-r requirements.txt
pytest>=8.0.0
pytest-mock>=3.12.0
yt-dlp>=2024.0.0
```

- [ ] **Step 5: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 6: Create empty `__init__.py` files**

Run:
```bash
mkdir -p src/lib tests scripts data .github/workflows
touch src/__init__.py src/lib/__init__.py tests/__init__.py scripts/__init__.py
```

- [ ] **Step 7: Replace `README.md` with project skeleton**

```markdown
# bible-bot

매일 KST 06:00에 트위터로 성경 본문 + 낭독 음성 YouTube 링크를 발행하는 봇.

## 구조

- `src/` — 매일 GitHub Actions가 실행하는 코드
- `scripts/` — 1회성 준비 스크립트 (YouTube 크롤링, 1년치 일정 생성)
- `data/` — 로컬 참조 데이터 (성경 본문, 비디오 매핑)
- `tests/` — pytest 테스트

## 셋업

1. [외부 계정 가이드](docs/setup/) 따라 X Developer + Google Cloud 셋업
2. `pip install -r requirements-dev.txt`
3. 자세한 설계: [docs/superpowers/specs/2026-04-29-bible-twitter-bot-design.md](docs/superpowers/specs/2026-04-29-bible-twitter-bot-design.md)
4. 구현 계획: [docs/superpowers/plans/2026-04-29-bible-twitter-bot.md](docs/superpowers/plans/2026-04-29-bible-twitter-bot.md)

## 실행

```bash
# 테스트
pytest

# 오늘의 트윗 미리보기 (실제 발행 안 함)
python -m src.post_today --dry-run

# 1년치 일정 생성 (1회성)
python -m scripts.build_schedule --year 2026
```
```

- [ ] **Step 8: First commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt pytest.ini README.md src/ tests/ scripts/ docs/
git commit -m "chore: project scaffolding and setup docs"
```

Expected: 커밋 성공.

---

## Task 3: `models.py` — `ScheduleEntry` + `BibleRef` 파서

성경 출처 문자열("창세기 1:1-3", "시편 23:1") 파싱이 build_schedule와 tweet_builder 양쪽에서 필요하므로 공용 모델로 분리.

**Files:**
- Create: `src/lib/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lib.models'`

- [ ] **Step 3: Implement `src/lib/models.py`**

```python
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


_REF_PATTERN = re.compile(
    r"^\s*(?P<book>[^\d\s]+)\s+(?P<chapter>\d+)(?::(?P<vstart>\d+)(?:-(?P<vend>\d+))?)?\s*$"
)


@dataclass(frozen=True)
class BibleRef:
    book: str
    chapter: int
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None

    @classmethod
    def parse(cls, text: str) -> "BibleRef":
        m = _REF_PATTERN.match(text)
        if not m:
            raise ValueError(f"Invalid Bible reference: {text!r}")
        book = m.group("book")
        chapter = int(m.group("chapter"))
        vstart = int(m.group("vstart")) if m.group("vstart") else None
        vend = int(m.group("vend")) if m.group("vend") else vstart
        return cls(book=book, chapter=chapter, verse_start=vstart, verse_end=vend)

    def format(self) -> str:
        if self.verse_start is None:
            return f"{self.book} {self.chapter}"
        if self.verse_end == self.verse_start:
            return f"{self.book} {self.chapter}:{self.verse_start}"
        return f"{self.book} {self.chapter}:{self.verse_start}-{self.verse_end}"


@dataclass
class ScheduleEntry:
    date: date
    day_kind: str        # "meaningful" or "regular"
    label: str
    bible_ref: str
    bible_text: str
    youtube_url: str
    char_count: int = 0
    needs_thread: bool = False
    posted_at: Optional[datetime] = None
    tweet_id: Optional[str] = None
    error: str = ""

    def already_posted(self) -> bool:
        return self.tweet_id is not None and self.tweet_id != ""
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/models.py tests/test_models.py
git commit -m "feat(models): ScheduleEntry and BibleRef parser"
```

---

## Task 4: `tweet_builder` — 가중 글자수 카운터 (CJK 2 weight, URL 23)

**Files:**
- Create: `src/lib/tweet_builder.py`
- Test: `tests/test_tweet_builder_count.py`

- [ ] **Step 1: Write failing tests**

`tests/test_tweet_builder_count.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_tweet_builder_count.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/lib/tweet_builder.py`** (count function only)

```python
"""트윗 본문 조립 + 글자수 계산 + 스레드 분할.

twitter-text 규칙 (가중 카운트):
- ASCII 일반 문자: 1 weight
- CJK / 이모지 / 기타: 2 weight
- URL: 항상 23 weight (실제 길이 무관, t.co로 단축됨)
- 최대: 280 weight
"""
from __future__ import annotations
import re

# URL detection: https?://... (간단한 휴리스틱; 트위터 자체 단축 규칙과 동일하게 동작)
_URL_RE = re.compile(r"https?://\S+")
URL_WEIGHT = 23

# weight=1 ranges per twitter-text spec
_WEIGHT_ONE_RANGES = (
    (0x0000, 0x10FF),
    (0x2000, 0x200D),
    (0x2010, 0x201F),
    (0x2032, 0x2037),
)


def _char_weight(ch: str) -> int:
    cp = ord(ch)
    for lo, hi in _WEIGHT_ONE_RANGES:
        if lo <= cp <= hi:
            return 1
    return 2


def weighted_count(text: str) -> int:
    """트위터의 weighted character count 규칙 적용."""
    # URL은 23 weight로 치환한 뒤 카운트
    total = 0
    last = 0
    for m in _URL_RE.finditer(text):
        # URL 앞쪽 일반 텍스트
        for ch in text[last:m.start()]:
            total += _char_weight(ch)
        total += URL_WEIGHT
        last = m.end()
    # 마지막 URL 이후 텍스트
    for ch in text[last:]:
        total += _char_weight(ch)
    return total
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_tweet_builder_count.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/tweet_builder.py tests/test_tweet_builder_count.py
git commit -m "feat(tweet_builder): weighted character counting per twitter-text rules"
```

---

## Task 5: `tweet_builder` — 단일 트윗 조립

**Files:**
- Modify: `src/lib/tweet_builder.py`
- Test: `tests/test_tweet_builder_single.py`

- [ ] **Step 1: Write failing tests**

`tests/test_tweet_builder_single.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_tweet_builder_single.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_single'`

- [ ] **Step 3: Add to `src/lib/tweet_builder.py`** (append after existing code)

```python


def render_template(template: str, entry) -> str:
    """템플릿에 entry 필드를 채워 넣음. 리터럴 '\\n' 도 줄바꿈으로 변환."""
    # 리터럴 백슬래시-n을 진짜 줄바꿈으로 (Sheets 셀에서 입력된 경우)
    real_template = template.replace("\\n", "\n")
    return real_template.format(
        bible_text=entry.bible_text,
        bible_ref=entry.bible_ref,
        youtube_url=entry.youtube_url,
        label=entry.label,
    )


def build_single(entry, template: str) -> str:
    """단일 트윗 텍스트를 만든다 (길이 검증은 caller가)."""
    return render_template(template, entry)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_tweet_builder_single.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/tweet_builder.py tests/test_tweet_builder_single.py
git commit -m "feat(tweet_builder): single tweet assembly with template rendering"
```

---

## Task 6: `tweet_builder` — 절(verse) 경계 스레드 분할

**Files:**
- Modify: `src/lib/tweet_builder.py`
- Test: `tests/test_tweet_builder_thread.py`

- [ ] **Step 1: Write failing tests**

`tests/test_tweet_builder_thread.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_tweet_builder_thread.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_thread'`

- [ ] **Step 3: Add to `src/lib/tweet_builder.py`** (append)

```python


def _split_text_into_chunks(text: str, max_weight: int) -> list[str]:
    """본문을 절(개행) → 문장(. ! ?) → 어절(공백) 순으로 분할."""
    if weighted_count(text) <= max_weight:
        return [text]

    # 1차: 줄바꿈(절) 단위
    lines = text.split("\n")
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = current + ("\n" if current else "") + line
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # 한 줄 자체가 너무 긴 경우 → 문장 단위로 더 분할
            if weighted_count(line) > max_weight:
                chunks.extend(_split_by_sentences(line, max_weight))
                current = ""
            else:
                current = line
    if current:
        chunks.append(current)
    return chunks


def _split_by_sentences(line: str, max_weight: int) -> list[str]:
    """문장 부호(. ! ?) 기준 분할. 그래도 길면 어절."""
    parts = re.split(r"(?<=[.!?。！？])\s+", line)
    chunks: list[str] = []
    current = ""
    for p in parts:
        candidate = (current + " " + p).strip() if current else p
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if weighted_count(p) > max_weight:
                chunks.extend(_split_by_words(p, max_weight))
                current = ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


def _split_by_words(text: str, max_weight: int) -> list[str]:
    """공백 기준 분할. 마지막 수단."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip() if current else w
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = w  # Single word may exceed limit but we accept (rare in Korean)
    if current:
        chunks.append(current)
    return chunks


def build_thread(entry, template: str, max_weight: int = 270) -> list[str]:
    """단일 또는 복수 트윗으로 조립. 첫 트윗에 ref + URL, 이어지는 부분은 본문만.

    스레드일 때 각 트윗 끝에 (N/총) 표기.
    """
    single = render_template(template, entry)
    if weighted_count(single) <= max_weight:
        return [single]

    # 스레드 모드: bible_text를 분할, 각 chunk를 별도 트윗으로
    chunks = _split_text_into_chunks(entry.bible_text, _budget_for_text(entry, max_weight))

    if len(chunks) == 1:
        # Splitting failed to reduce; fall back to including everything
        return [single]

    parts: list[str] = []
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        suffix = f"\n\n({i}/{total})"
        if i == 1:
            # 첫 트윗: 본문 + ref + URL + 번호
            body = f"{chunk}\n\n— {entry.bible_ref}\n\n🎧 {entry.youtube_url}{suffix}"
        else:
            # 이어지는 트윗: 본문 + 번호만
            body = f"{chunk}{suffix}"
        parts.append(body)
    return parts


def _budget_for_text(entry, max_weight: int) -> int:
    """첫 트윗에 ref + URL + 번호가 들어가므로 본문에 쓸 수 있는 최대 weight 계산."""
    # 보수적: ref + URL + 줄바꿈 + 번호 표기까지 ~ 60 weight 예약
    overhead = weighted_count(f"\n\n— {entry.bible_ref}\n\n🎧 {entry.youtube_url}\n\n(99/99)")
    return max(50, max_weight - overhead)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_tweet_builder_thread.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run all tweet_builder tests**

Run: `pytest tests/test_tweet_builder*.py -v`
Expected: PASS (all 20 tests)

- [ ] **Step 6: Commit**

```bash
git add src/lib/tweet_builder.py tests/test_tweet_builder_thread.py
git commit -m "feat(tweet_builder): thread splitting at verse/sentence/word boundaries"
```

---

## Task 7: `tweet_builder` 공개 API — `build()` (단일/스레드 자동 결정)

**Files:**
- Modify: `src/lib/tweet_builder.py`
- Test: `tests/test_tweet_builder_build.py`

- [ ] **Step 1: Write failing tests**

`tests/test_tweet_builder_build.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_tweet_builder_build.py -v`
Expected: FAIL — `ImportError: cannot import name 'build'`

- [ ] **Step 3: Add to `src/lib/tweet_builder.py`** (append)

```python


def build(entry, template: str, max_weight: int = 270) -> list[str]:
    """공개 API. 단일 또는 스레드 트윗 리스트 반환."""
    return build_thread(entry, template, max_weight)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_tweet_builder_build.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/tweet_builder.py tests/test_tweet_builder_build.py
git commit -m "feat(tweet_builder): public build() API"
```

---

## Task 8: `twitter_client.py` — tweepy 래퍼 + Mock 테스트

**Files:**
- Create: `src/lib/twitter_client.py`
- Test: `tests/test_twitter_client.py`

- [ ] **Step 1: Write failing tests**

`tests/test_twitter_client.py`:
```python
from unittest.mock import MagicMock, patch
import pytest
from src.lib.twitter_client import TwitterClient, DuplicateTweetError


def make_client(mock_api):
    """Helper: TwitterClient with a mocked tweepy.Client injected."""
    c = TwitterClient(
        api_key="k", api_secret="s",
        access_token="t", access_token_secret="ts",
        _client=mock_api,
    )
    return c


def test_post_tweet_success():
    mock_api = MagicMock()
    mock_api.create_tweet.return_value.data = {"id": "1234567890"}
    c = make_client(mock_api)
    tweet_id = c.post_tweet("hello")
    assert tweet_id == "1234567890"
    mock_api.create_tweet.assert_called_once_with(text="hello")


def test_post_thread_chains_replies():
    mock_api = MagicMock()
    # Each call returns a different ID
    mock_api.create_tweet.side_effect = [
        MagicMock(data={"id": "111"}),
        MagicMock(data={"id": "222"}),
        MagicMock(data={"id": "333"}),
    ]
    c = make_client(mock_api)
    ids = c.post_thread(["a", "b", "c"])
    assert ids == ["111", "222", "333"]
    # Verify reply chain
    calls = mock_api.create_tweet.call_args_list
    assert calls[0].kwargs == {"text": "a"}
    assert calls[1].kwargs == {"text": "b", "in_reply_to_tweet_id": "111"}
    assert calls[2].kwargs == {"text": "c", "in_reply_to_tweet_id": "222"}


def test_duplicate_tweet_raises_specific_error():
    import tweepy
    mock_api = MagicMock()
    # Simulate tweepy raising Forbidden with duplicate-content code
    err = tweepy.errors.Forbidden(MagicMock(status_code=403, text="duplicate content"))
    err.api_codes = [187]
    mock_api.create_tweet.side_effect = err
    c = make_client(mock_api)
    with pytest.raises(DuplicateTweetError):
        c.post_tweet("hello")
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_twitter_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.lib.twitter_client'`

- [ ] **Step 3: Implement `src/lib/twitter_client.py`**

```python
"""Twitter API v2 wrapper around tweepy."""
from __future__ import annotations
import time
import logging
from typing import Optional

import tweepy

log = logging.getLogger(__name__)


class DuplicateTweetError(Exception):
    """Twitter rejected post as duplicate (error code 187)."""


class TwitterClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
        _client: Optional[tweepy.Client] = None,
        max_retries: int = 3,
    ):
        # _client lets tests inject a mock
        self._api = _client or tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        self.max_retries = max_retries

    def post_tweet(self, text: str, in_reply_to_tweet_id: Optional[str] = None) -> str:
        """Returns the new tweet's ID. Raises DuplicateTweetError on 187."""
        kwargs = {"text": text}
        if in_reply_to_tweet_id:
            kwargs["in_reply_to_tweet_id"] = in_reply_to_tweet_id

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self._api.create_tweet(**kwargs)
                return str(resp.data["id"])
            except tweepy.errors.Forbidden as e:
                if 187 in (getattr(e, "api_codes", []) or []):
                    raise DuplicateTweetError(str(e)) from e
                last_err = e
                break  # Forbidden is not retryable (auth issue)
            except tweepy.errors.TooManyRequests as e:
                last_err = e
                wait = 2 ** attempt
                log.warning("Rate limited, sleeping %ds", wait)
                time.sleep(wait)
            except tweepy.errors.TweepyException as e:
                last_err = e
                wait = 2 ** attempt
                log.warning("Twitter API error (attempt %d): %s — sleeping %ds",
                            attempt + 1, e, wait)
                time.sleep(wait)
        raise RuntimeError(f"post_tweet failed after {self.max_retries} attempts") from last_err

    def post_thread(self, texts: list[str]) -> list[str]:
        """Posts a chain of replies. Returns list of tweet IDs in order."""
        ids: list[str] = []
        prev_id: Optional[str] = None
        for text in texts:
            tid = self.post_tweet(text, in_reply_to_tweet_id=prev_id)
            ids.append(tid)
            prev_id = tid
        return ids
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_twitter_client.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/twitter_client.py tests/test_twitter_client.py
git commit -m "feat(twitter_client): tweepy wrapper with retry and duplicate detection"
```

---

## Task 9: `sheets_client.py` — gspread 래퍼 + Mock 테스트

**Files:**
- Create: `src/lib/sheets_client.py`
- Test: `tests/test_sheets_client.py`

- [ ] **Step 1: Write failing tests**

`tests/test_sheets_client.py`:
```python
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from src.lib.sheets_client import SheetsClient
from src.lib.models import ScheduleEntry


def make_client(mock_spreadsheet):
    return SheetsClient(creds_dict={}, sheet_id="x", _spreadsheet=mock_spreadsheet)


def test_get_today_row_returns_entry():
    # Mock the schedule worksheet's records
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {
            "date": "2026-01-01", "day_kind": "meaningful",
            "label": "새해 새 마음", "bible_ref": "빌립보서 3:13-14",
            "bible_text": "형제들아", "youtube_url": "https://youtu.be/abc",
            "char_count": 100, "needs_thread": "FALSE",
            "posted_at": "", "tweet_id": "", "error": "",
        },
        {
            "date": "2026-01-02", "day_kind": "regular",
            "label": "", "bible_ref": "시편 1:1",
            "bible_text": "복 있는 사람은", "youtube_url": "https://youtu.be/xyz",
            "char_count": 50, "needs_thread": "FALSE",
            "posted_at": "", "tweet_id": "", "error": "",
        },
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)

    entry = c.get_row(date(2026, 1, 2))
    assert entry is not None
    assert entry.bible_ref == "시편 1:1"
    assert entry.day_kind == "regular"
    assert entry.tweet_id is None  # Empty string converted to None


def test_get_today_row_missing_returns_none():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = []
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)
    assert c.get_row(date(2026, 1, 1)) is None


def test_update_row_writes_correct_cells():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {"date": "2026-01-01", "day_kind": "regular", "label": "",
         "bible_ref": "x", "bible_text": "y", "youtube_url": "z",
         "char_count": 0, "needs_thread": "FALSE",
         "posted_at": "", "tweet_id": "", "error": ""}
    ]
    # Header row (1) + first data row (2)
    mock_ws.row_values.return_value = [
        "date", "day_kind", "label", "bible_ref", "bible_text",
        "youtube_url", "char_count", "needs_thread",
        "posted_at", "tweet_id", "error"
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)

    posted_at = datetime(2026, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
    c.update_row(date(2026, 1, 1), posted_at=posted_at, tweet_id="9999")

    # Verify update_cell was called for posted_at and tweet_id columns
    calls = mock_ws.update_cell.call_args_list
    # row index = 2 (header is 1), columns: posted_at=9, tweet_id=10
    assert (2, 9, posted_at.isoformat()) in [c.args for c in calls]
    assert (2, 10, "9999") in [c.args for c in calls]


def test_get_config_returns_dict():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {"key": "timezone", "value": "Asia/Seoul"},
        {"key": "tweet_template", "value": "{bible_text}\\n— {bible_ref}"},
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)
    config = c.get_config()
    assert config["timezone"] == "Asia/Seoul"
    assert "{bible_text}" in config["tweet_template"]
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_sheets_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/lib/sheets_client.py`**

```python
"""Google Sheets wrapper using gspread."""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Any

import gspread
from google.oauth2.service_account import Credentials

from src.lib.models import ScheduleEntry


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _empty_to_none(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    return str(v)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class SheetsClient:
    def __init__(self, creds_dict: dict, sheet_id: str, _spreadsheet=None):
        # _spreadsheet allows test injection
        if _spreadsheet is not None:
            self._ss = _spreadsheet
        else:
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            client = gspread.authorize(creds)
            self._ss = client.open_by_key(sheet_id)

    def get_row(self, target_date: date) -> Optional[ScheduleEntry]:
        ws = self._ss.worksheet("schedule")
        records = ws.get_all_records()
        target_str = target_date.isoformat()
        for rec in records:
            if str(rec.get("date")) == target_str:
                return self._record_to_entry(rec)
        return None

    def update_row(self, target_date: date, **fields):
        ws = self._ss.worksheet("schedule")
        records = ws.get_all_records()
        header = ws.row_values(1)
        col_idx = {name: i + 1 for i, name in enumerate(header)}

        target_str = target_date.isoformat()
        row_num = None
        for i, rec in enumerate(records, start=2):  # row 1 is header
            if str(rec.get("date")) == target_str:
                row_num = i
                break
        if row_num is None:
            raise ValueError(f"No row for date {target_date}")

        for key, value in fields.items():
            if key not in col_idx:
                raise ValueError(f"Unknown column: {key}")
            if isinstance(value, datetime):
                value = value.isoformat()
            ws.update_cell(row_num, col_idx[key], str(value) if value is not None else "")

    def get_config(self) -> dict:
        ws = self._ss.worksheet("config")
        records = ws.get_all_records()
        return {r["key"]: r["value"] for r in records}

    def get_meaningful_days(self) -> list[dict]:
        ws = self._ss.worksheet("meaningful_days")
        return ws.get_all_records()

    def write_schedule_rows(self, rows: list[dict]):
        """Replace entire schedule tab with given rows. Used by build_schedule."""
        ws = self._ss.worksheet("schedule")
        if not rows:
            return
        header = list(rows[0].keys())
        values = [header] + [[str(r.get(h, "")) for h in header] for r in rows]
        ws.clear()
        ws.update("A1", values)

    def _record_to_entry(self, rec: dict) -> ScheduleEntry:
        return ScheduleEntry(
            date=date.fromisoformat(str(rec["date"])),
            day_kind=str(rec.get("day_kind", "regular")),
            label=str(rec.get("label", "") or ""),
            bible_ref=str(rec.get("bible_ref", "")),
            bible_text=str(rec.get("bible_text", "")),
            youtube_url=str(rec.get("youtube_url", "")),
            char_count=int(rec.get("char_count") or 0),
            needs_thread=str(rec.get("needs_thread", "")).upper() == "TRUE",
            posted_at=_parse_dt(str(rec.get("posted_at", "") or "")),
            tweet_id=_empty_to_none(rec.get("tweet_id")),
            error=str(rec.get("error", "") or ""),
        )
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_sheets_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/lib/sheets_client.py tests/test_sheets_client.py
git commit -m "feat(sheets_client): gspread wrapper for schedule, config, meaningful_days"
```

---

## Task 10: `post_today.py` — 매일 실행 메인 + 멱등성

**Files:**
- Create: `src/post_today.py`
- Test: `tests/test_post_today.py`

- [ ] **Step 1: Write failing tests**

`tests/test_post_today.py`:
```python
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from src.post_today import run_post
from src.lib.models import ScheduleEntry
from src.lib.twitter_client import DuplicateTweetError


def make_entry(tweet_id=None, posted_at=None) -> ScheduleEntry:
    return ScheduleEntry(
        date=date(2026, 1, 1), day_kind="regular", label="",
        bible_ref="시편 1:1", bible_text="복 있는 사람은",
        youtube_url="https://youtu.be/abc",
        tweet_id=tweet_id, posted_at=posted_at,
    )


def test_skips_if_already_posted():
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry(tweet_id="9999")
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()

    result = run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)

    assert result["status"] == "skipped"
    twitter.post_thread.assert_not_called()


def test_returns_error_if_no_row_for_date():
    sheets = MagicMock()
    sheets.get_row.return_value = None
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()

    result = run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)
    assert result["status"] == "error"
    assert "no row" in result["message"].lower()


def test_posts_tweet_and_updates_sheet():
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry()
    sheets.get_config.return_value = {
        "tweet_template": "{bible_text}\n— {bible_ref}\n🎧 {youtube_url}"
    }
    twitter = MagicMock()
    twitter.post_thread.return_value = ["12345"]

    result = run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)

    assert result["status"] == "posted"
    assert result["tweet_ids"] == ["12345"]
    sheets.update_row.assert_called_once()
    update_kwargs = sheets.update_row.call_args.kwargs
    assert update_kwargs["tweet_id"] == "12345"
    assert "posted_at" in update_kwargs


def test_dry_run_does_not_post():
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry()
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()

    result = run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=True)

    assert result["status"] == "dry_run"
    assert "tweets" in result
    twitter.post_thread.assert_not_called()
    sheets.update_row.assert_not_called()


def test_duplicate_error_records_in_sheet_and_raises():
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry()
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()
    twitter.post_thread.side_effect = DuplicateTweetError("dup")

    with pytest.raises(DuplicateTweetError):
        run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)

    sheets.update_row.assert_called_once()
    update_kwargs = sheets.update_row.call_args.kwargs
    assert "DUPLICATE" in update_kwargs["error"].upper()


def test_generic_failure_records_error_and_raises():
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry()
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()
    twitter.post_thread.side_effect = RuntimeError("network down")

    with pytest.raises(RuntimeError):
        run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)

    sheets.update_row.assert_called_once()
    update_kwargs = sheets.update_row.call_args.kwargs
    assert "network down" in update_kwargs["error"]
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_post_today.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `src/post_today.py`**

```python
"""Daily posting entry point — invoked by GitHub Actions cron."""
from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.lib.sheets_client import SheetsClient
from src.lib.twitter_client import TwitterClient, DuplicateTweetError
from src.lib import tweet_builder

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
DEFAULT_TEMPLATE = "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}"
DEFAULT_MAX_WEIGHT = 270


def today_kst() -> date:
    return datetime.now(KST).date()


def run_post(sheets: SheetsClient, twitter: TwitterClient,
             target_date: date, dry_run: bool = False) -> dict:
    entry = sheets.get_row(target_date)
    if entry is None:
        msg = f"No row found in schedule for {target_date}"
        log.error(msg)
        return {"status": "error", "message": msg}

    if entry.already_posted():
        log.info("Already posted today: tweet_id=%s", entry.tweet_id)
        return {"status": "skipped", "tweet_id": entry.tweet_id}

    config = sheets.get_config()
    template = config.get("tweet_template", DEFAULT_TEMPLATE)
    max_weight = int(config.get("safety_margin_weight", DEFAULT_MAX_WEIGHT))

    tweets = tweet_builder.build(entry, template, max_weight=max_weight)
    log.info("Built %d tweet part(s) for %s", len(tweets), target_date)

    if dry_run:
        return {"status": "dry_run", "tweets": tweets, "count": len(tweets)}

    try:
        ids = twitter.post_thread(tweets)
        log.info("Posted: %s", ids)
    except DuplicateTweetError as e:
        sheets.update_row(target_date, error=f"DUPLICATE_DETECTED: {e}")
        raise
    except Exception as e:
        sheets.update_row(target_date, error=f"{type(e).__name__}: {e}")
        raise

    sheets.update_row(
        target_date,
        posted_at=datetime.now(timezone.utc),
        tweet_id=ids[0],
        error="",
    )
    return {"status": "posted", "tweet_ids": ids, "count": len(ids)}


def _build_clients() -> tuple[SheetsClient, TwitterClient]:
    creds_json = os.environ["GOOGLE_SHEETS_CREDS"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    creds = json.loads(creds_json)
    sheets = SheetsClient(creds_dict=creds, sheet_id=sheet_id)
    twitter = TwitterClient(
        api_key=os.environ["TWITTER_API_KEY"],
        api_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_SECRET"],
    )
    return sheets, twitter


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not actually post; print tweet content")
    parser.add_argument("--date", type=str, default=None,
                        help="Override target date (YYYY-MM-DD KST)")
    args = parser.parse_args(argv)

    target = date.fromisoformat(args.date) if args.date else today_kst()
    log.info("Target date (KST): %s, dry_run=%s", target, args.dry_run)

    sheets, twitter = _build_clients()
    result = run_post(sheets, twitter, target_date=target, dry_run=args.dry_run)

    if args.dry_run:
        for i, t in enumerate(result["tweets"], 1):
            print(f"\n--- Tweet {i}/{result['count']} ---\n{t}\n")

    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_post_today.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run all tests**

Run: `pytest -v`
Expected: PASS — total ~37 tests across all files

- [ ] **Step 6: Commit**

```bash
git add src/post_today.py tests/test_post_today.py
git commit -m "feat(post_today): daily posting orchestration with idempotency and dry-run"
```

---

## Task 11: `crawl_youtube.py` — 채널 크롤링 → CSV

**Files:**
- Create: `scripts/crawl_youtube.py`
- Test: `tests/test_crawl_youtube.py`

- [ ] **Step 1: Write failing tests**

`tests/test_crawl_youtube.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_crawl_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `scripts/crawl_youtube.py`**

```python
"""YouTube channel crawler — outputs data/youtube_videos.csv.

Usage:
    python -m scripts.crawl_youtube --channel <CHANNEL_URL>
"""
from __future__ import annotations
import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Optional

# Title parser: matches "<책이름> <숫자>장" (allowing trailing extras)
# Korean book name: any non-digit non-space sequence
_TITLE_RE = re.compile(r"^\s*([^\d\s]+(?:[^\d\s]+)*)\s+(\d+)장")


def parse_title(title: str) -> Optional[tuple[str, int]]:
    """Returns (book, chapter) or None."""
    m = _TITLE_RE.match(title)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def crawl_channel(channel_url: str) -> list[dict]:
    """Use yt-dlp to enumerate channel videos. Returns list of {book, chapter, video_id, video_url, title}."""
    import yt_dlp

    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
    }
    rows: list[dict] = []
    skipped: list[str] = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries", [])
        # Some channels have nested entries (tabs); flatten one level
        flat = []
        for e in entries:
            if e and e.get("_type") == "playlist":
                flat.extend(e.get("entries") or [])
            elif e:
                flat.append(e)

        for v in flat:
            title = v.get("title", "")
            vid = v.get("id", "")
            parsed = parse_title(title)
            if not parsed:
                skipped.append(title)
                continue
            book, chapter = parsed
            rows.append({
                "book": book,
                "chapter": chapter,
                "video_id": vid,
                "video_url": f"https://youtu.be/{vid}",
                "title": title,
            })

    print(f"Parsed: {len(rows)} videos, Skipped: {len(skipped)}")
    if skipped:
        print("Skipped titles (first 10):")
        for t in skipped[:10]:
            print(f"  - {t}")
    return rows


def write_csv(rows: list[dict], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["book", "chapter", "video_id", "video_url", "title"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} rows to {output_path}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, help="YouTube channel URL")
    parser.add_argument("--out", type=Path, default=Path("data/youtube_videos.csv"))
    args = parser.parse_args(argv)

    rows = crawl_channel(args.channel)
    if not rows:
        print("WARNING: 0 videos parsed. Check channel URL or title format.", file=sys.stderr)
        sys.exit(1)
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_crawl_youtube.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/crawl_youtube.py tests/test_crawl_youtube.py
git commit -m "feat(crawl_youtube): YouTube channel crawler with title parser"
```

> **Manual verification (deferred until user provides channel URL):**
> ```bash
> python -m scripts.crawl_youtube --channel "https://www.youtube.com/@USERCHANNEL/videos"
> head -5 data/youtube_videos.csv
> ```

---

## Task 12: `build_schedule.py` — 날짜 + 시편/잠언 순환 알고리즘

**Files:**
- Create: `scripts/build_schedule.py`
- Test: `tests/test_build_schedule.py`

이 task는 build_schedule의 **순수 로직** (날짜 생성, 순환 알고리즘) 만 다룸. 외부 데이터 통합은 Task 13.

- [ ] **Step 1: Write failing tests**

`tests/test_build_schedule.py`:
```python
from datetime import date
from scripts.build_schedule import (
    generate_dates_for_year,
    psalms_proverbs_cycle,
    cycle_ref_for_day_index,
)


class TestGenerateDates:
    def test_normal_year(self):
        dates = list(generate_dates_for_year(2025))
        assert len(dates) == 365
        assert dates[0] == date(2025, 1, 1)
        assert dates[-1] == date(2025, 12, 31)

    def test_leap_year(self):
        dates = list(generate_dates_for_year(2028))
        assert len(dates) == 366
        assert date(2028, 2, 29) in dates


class TestPsalmsProverbsCycle:
    def test_total_count(self):
        # 시편 150편 + 잠언 31장 = 181 entries
        cycle = psalms_proverbs_cycle()
        assert len(cycle) == 181

    def test_first_is_psalm_one(self):
        cycle = psalms_proverbs_cycle()
        assert cycle[0] == ("시편", 1)

    def test_psalm_150_then_proverbs(self):
        cycle = psalms_proverbs_cycle()
        assert cycle[149] == ("시편", 150)
        assert cycle[150] == ("잠언", 1)
        assert cycle[180] == ("잠언", 31)


class TestCycleRefForDayIndex:
    def test_first_day(self):
        # day_index 0 → 시편 1
        assert cycle_ref_for_day_index(0) == "시편 1"

    def test_wraps_around(self):
        # day_index 181 → wraps back to 시편 1
        assert cycle_ref_for_day_index(181) == "시편 1"
        assert cycle_ref_for_day_index(182) == "시편 2"

    def test_proverbs(self):
        # day_index 150 → 잠언 1
        assert cycle_ref_for_day_index(150) == "잠언 1"
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_build_schedule.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `scripts/build_schedule.py` (skeleton + cycle logic)**

```python
"""1년치 일정 생성 → Google Sheets에 업로드.

Usage:
    python -m scripts.build_schedule --year 2026
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta
from typing import Iterator


def generate_dates_for_year(year: int) -> Iterator[date]:
    """1월 1일부터 12월 31일까지의 모든 날짜."""
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        yield d
        d += timedelta(days=1)


def psalms_proverbs_cycle() -> list[tuple[str, int]]:
    """시편 1편 ~ 시편 150편, 잠언 1장 ~ 잠언 31장 = 총 181개."""
    cycle: list[tuple[str, int]] = []
    for ch in range(1, 151):
        cycle.append(("시편", ch))
    for ch in range(1, 32):
        cycle.append(("잠언", ch))
    return cycle


_CYCLE_CACHE: list[tuple[str, int]] | None = None


def cycle_ref_for_day_index(day_index: int) -> str:
    """day_index 0-based로 순환에서 ref 반환 (예: '시편 1', '잠언 5')."""
    global _CYCLE_CACHE
    if _CYCLE_CACHE is None:
        _CYCLE_CACHE = psalms_proverbs_cycle()
    book, chapter = _CYCLE_CACHE[day_index % len(_CYCLE_CACHE)]
    return f"{book} {chapter}"
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_build_schedule.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_schedule.py tests/test_build_schedule.py
git commit -m "feat(build_schedule): date generation and Psalms/Proverbs cycle"
```

---

## Task 13: `build_schedule.py` — 의미있는 날 매칭 + 본문 + URL 통합

**Files:**
- Modify: `scripts/build_schedule.py`
- Test: `tests/test_build_schedule_integrate.py`

- [ ] **Step 1: Write failing tests**

`tests/test_build_schedule_integrate.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_build_schedule_integrate.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add to `scripts/build_schedule.py`** (append)

```python


from src.lib.models import BibleRef
from src.lib.tweet_builder import weighted_count


class BibleTextLookup:
    """{(book, chapter, verse): text} lookup."""
    def __init__(self, data: dict[tuple[str, int, int], str]):
        self._data = dict(data)

    def get(self, book: str, chapter: int, verse: int) -> str:
        return self._data.get((book, chapter, verse), "")

    def chapter_verses(self, book: str, chapter: int) -> list[tuple[int, str]]:
        """Return all (verse_num, text) for a chapter, sorted by verse_num."""
        items = [(v, t) for (b, c, v), t in self._data.items() if b == book and c == chapter]
        return sorted(items, key=lambda x: x[0])


class YoutubeUrlLookup:
    """{(book, chapter): url}"""
    def __init__(self, data: dict[tuple[str, int], str]):
        self._data = dict(data)

    def get(self, book: str, chapter: int) -> str:
        return self._data.get((book, chapter), "")


def match_meaningful_day(d: date, meaningful_days: list[dict]) -> dict | None:
    """Return matching meaningful day record or None."""
    pattern = d.strftime("%m-%d")
    for entry in meaningful_days:
        if str(entry.get("pattern", "")).strip() == pattern:
            return entry
    return None


def pick_first_n_verses(lookup: BibleTextLookup, book: str, chapter: int,
                         n: int = 3) -> tuple[str, str]:
    """Return (ref_string, joined_text) for first N verses of a chapter."""
    verses = lookup.chapter_verses(book, chapter)
    if not verses:
        return f"{book} {chapter}", ""
    selected = verses[:n]
    texts = [t for _, t in selected]
    if len(selected) == 1:
        ref = f"{book} {chapter}:{selected[0][0]}"
    else:
        ref = f"{book} {chapter}:{selected[0][0]}-{selected[-1][0]}"
    return ref, "\n".join(texts)


def parse_suggested_refs(s: str) -> list[str]:
    """Comma-separated refs from sheet → list, picks first."""
    return [r.strip() for r in str(s or "").split(",") if r.strip()]


def resolve_meaningful_text(lookup: BibleTextLookup, ref_str: str) -> tuple[str, str]:
    """Given a ref string like '빌립보서 3:13-14', return (formatted_ref, joined_text)."""
    try:
        ref = BibleRef.parse(ref_str)
    except ValueError:
        return ref_str, ""
    if ref.verse_start is None:
        # Whole chapter — pick first 3 verses
        return pick_first_n_verses(lookup, ref.book, ref.chapter, n=3)
    texts = []
    for v in range(ref.verse_start, (ref.verse_end or ref.verse_start) + 1):
        t = lookup.get(ref.book, ref.chapter, v)
        if t:
            texts.append(t)
    return ref.format(), "\n".join(texts)


class ScheduleBuilder:
    def __init__(self, bible: BibleTextLookup, youtube: YoutubeUrlLookup,
                 meaningful_days: list[dict], template: str):
        self.bible = bible
        self.youtube = youtube
        self.meaningful_days = meaningful_days
        self.template = template
        self.summary = {
            "total": 0,
            "meaningful": 0,
            "regular": 0,
            "needs_thread": 0,
            "missing_youtube": [],
            "missing_text": [],
        }

    def build_year(self, year: int) -> list[dict]:
        rows: list[dict] = []
        regular_index = 0
        for d in generate_dates_for_year(year):
            mday = match_meaningful_day(d, self.meaningful_days)
            if mday:
                refs = parse_suggested_refs(mday.get("suggested_refs", ""))
                ref_str = refs[0] if refs else ""
                ref_formatted, text = resolve_meaningful_text(self.bible, ref_str) if ref_str else ("", "")
                row = self._make_row(d, "meaningful", str(mday.get("name", "")),
                                      ref_formatted, text)
                self.summary["meaningful"] += 1
            else:
                ref_str = cycle_ref_for_day_index(regular_index)
                ref = BibleRef.parse(ref_str)
                ref_formatted, text = pick_first_n_verses(self.bible, ref.book, ref.chapter, n=3)
                row = self._make_row(d, "regular", "", ref_formatted, text)
                self.summary["regular"] += 1
                regular_index += 1
            rows.append(row)
            self.summary["total"] += 1
        return rows

    def _make_row(self, d: date, day_kind: str, label: str,
                  bible_ref: str, bible_text: str) -> dict:
        # Lookup youtube URL (parse book/chapter from ref)
        try:
            ref = BibleRef.parse(bible_ref)
            url = self.youtube.get(ref.book, ref.chapter)
            if not url:
                self.summary["missing_youtube"].append(f"{ref.book} {ref.chapter}")
        except ValueError:
            url = ""
        if not bible_text:
            self.summary["missing_text"].append(bible_ref)

        # Compute char_count by simulating template render
        rendered = self.template.replace("\\n", "\n").format(
            bible_text=bible_text, bible_ref=bible_ref,
            youtube_url=url, label=label,
        )
        cc = weighted_count(rendered)
        needs_thread = cc > 280
        if needs_thread:
            self.summary["needs_thread"] += 1

        return {
            "date": d.isoformat(),
            "day_kind": day_kind,
            "label": label,
            "bible_ref": bible_ref,
            "bible_text": bible_text,
            "youtube_url": url,
            "char_count": cc,
            "needs_thread": "TRUE" if needs_thread else "FALSE",
            "posted_at": "",
            "tweet_id": "",
            "error": "",
        }
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_build_schedule_integrate.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_schedule.py tests/test_build_schedule_integrate.py
git commit -m "feat(build_schedule): meaningful day matching, verse selection, builder"
```

---

## Task 14: `build_schedule.py` — CSV 로딩 + Sheet 업로드 + CLI

**Files:**
- Modify: `scripts/build_schedule.py`
- Test: `tests/test_build_schedule_io.py`

- [ ] **Step 1: Write failing tests**

`tests/test_build_schedule_io.py`:
```python
import csv
from pathlib import Path
from scripts.build_schedule import load_bible_csv, load_youtube_csv


def test_load_bible_csv(tmp_path: Path):
    p = tmp_path / "bible.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "text"])
        w.writerow(["창세기", "1", "1", "태초에 하나님이"])
        w.writerow(["창세기", "1", "2", "땅이 혼돈하고"])

    lookup = load_bible_csv(p)
    assert lookup.get("창세기", 1, 1) == "태초에 하나님이"
    assert lookup.get("창세기", 1, 2) == "땅이 혼돈하고"


def test_load_youtube_csv(tmp_path: Path):
    p = tmp_path / "yt.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "video_id", "video_url", "title"])
        w.writerow(["창세기", "1", "abc", "https://youtu.be/abc", "창세기 1장"])

    lookup = load_youtube_csv(p)
    assert lookup.get("창세기", 1) == "https://youtu.be/abc"
```

- [ ] **Step 2: Run tests — expect failure**

Run: `pytest tests/test_build_schedule_io.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Add to `scripts/build_schedule.py`** (append)

```python


import csv as _csv
import json as _json
import os
from pathlib import Path


def load_bible_csv(path: Path) -> BibleTextLookup:
    data: dict[tuple[str, int, int], str] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            book = row["book"].strip()
            chapter = int(row["chapter"])
            verse = int(row["verse"])
            text = row["text"]
            data[(book, chapter, verse)] = text
    return BibleTextLookup(data)


def load_youtube_csv(path: Path) -> YoutubeUrlLookup:
    data: dict[tuple[str, int], str] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            book = row["book"].strip()
            chapter = int(row["chapter"])
            url = row["video_url"]
            data[(book, chapter)] = url
    return YoutubeUrlLookup(data)


def print_summary(summary: dict):
    print()
    print(f"Built {summary['total']} schedule entries:")
    print(f"  📅 {summary['meaningful']} meaningful days, {summary['regular']} regular days")
    print(f"  🧵 {summary['needs_thread']} entries need thread (over 280 weight)")
    if summary["missing_youtube"]:
        unique = sorted(set(summary["missing_youtube"]))
        print(f"  ⚠️  {len(unique)} chapters missing YouTube URL:")
        for s in unique[:10]:
            print(f"        - {s}")
        if len(unique) > 10:
            print(f"        ...({len(unique) - 10} more)")
    if summary["missing_text"]:
        unique = sorted(set(summary["missing_text"]))
        print(f"  ⚠️  {len(unique)} refs missing bible text:")
        for s in unique[:10]:
            print(f"        - {s}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--bible-csv", type=Path, default=Path("data/bible_text.csv"))
    parser.add_argument("--youtube-csv", type=Path, default=Path("data/youtube_videos.csv"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print preview rows without uploading to Sheet")
    parser.add_argument("--preview-count", type=int, default=5)
    args = parser.parse_args(argv)

    if not args.bible_csv.exists():
        raise SystemExit(f"Bible CSV not found: {args.bible_csv}")
    if not args.youtube_csv.exists():
        raise SystemExit(f"YouTube CSV not found: {args.youtube_csv}")

    bible = load_bible_csv(args.bible_csv)
    yt = load_youtube_csv(args.youtube_csv)

    # Read meaningful_days + config from Sheet
    creds = _json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    from src.lib.sheets_client import SheetsClient
    sheets = SheetsClient(creds_dict=creds, sheet_id=sheet_id)
    meaningful = sheets.get_meaningful_days()
    config = sheets.get_config()
    template = config.get("tweet_template", "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}")

    builder = ScheduleBuilder(bible, yt, meaningful, template)
    rows = builder.build_year(args.year)

    if args.dry_run:
        print(f"DRY RUN — would upload {len(rows)} rows. First {args.preview_count}:")
        for r in rows[:args.preview_count]:
            print(r)
    else:
        sheets.write_schedule_rows(rows)
        print(f"Uploaded {len(rows)} rows to Sheet.")

    print_summary(builder.summary)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests — expect pass**

Run: `pytest tests/test_build_schedule_io.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run all tests**

Run: `pytest -v`
Expected: PASS — all tests across all files

- [ ] **Step 6: Commit**

```bash
git add scripts/build_schedule.py tests/test_build_schedule_io.py
git commit -m "feat(build_schedule): CSV loaders + sheet upload + CLI with summary"
```

---

## Task 15: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily-post.yml`

- [ ] **Step 1: Create workflow file**

`.github/workflows/daily-post.yml`:
```yaml
name: Daily Tweet

on:
  schedule:
    - cron: '0 21 * * *'   # UTC 21:00 = KST 06:00 (next day)
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run (no actual posting)'
        required: false
        default: 'false'
      target_date:
        description: 'Override target date (YYYY-MM-DD KST), blank = today'
        required: false
        default: ''

jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Cache pip
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run post_today
        env:
          GOOGLE_SHEETS_CREDS:    ${{ secrets.GOOGLE_SHEETS_CREDS }}
          GOOGLE_SHEET_ID:        ${{ secrets.GOOGLE_SHEET_ID }}
          TWITTER_API_KEY:        ${{ secrets.TWITTER_API_KEY }}
          TWITTER_API_SECRET:     ${{ secrets.TWITTER_API_SECRET }}
          TWITTER_ACCESS_TOKEN:   ${{ secrets.TWITTER_ACCESS_TOKEN }}
          TWITTER_ACCESS_SECRET:  ${{ secrets.TWITTER_ACCESS_SECRET }}
        run: |
          ARGS=""
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            ARGS="$ARGS --dry-run"
          fi
          if [ -n "${{ inputs.target_date }}" ]; then
            ARGS="$ARGS --date ${{ inputs.target_date }}"
          fi
          python -m src.post_today $ARGS
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/daily-post.yml
git commit -m "ci: daily posting workflow with cron and manual trigger"
```

---

## Task 16: 운영 시작 체크리스트 + Seed 데이터 가이드

**Files:**
- Create: `docs/setup/03-seed-meaningful-days.md`
- Create: `docs/setup/04-deployment-checklist.md`

- [ ] **Step 1: Create `docs/setup/03-seed-meaningful-days.md`**

```markdown
# 의미있는 날 시드 입력

Google Sheet의 `meaningful_days` 탭에 아래 헤더와 초기 데이터를 입력하세요. 본인이 추가/수정 가능합니다.

## 시트 헤더 (1행)

| pattern | name | suggested_refs | note |
|---|---|---|---|

## 초기 시드 (예시 — 자유롭게 수정/추가)

| pattern | name | suggested_refs | note |
|---|---|---|---|
| 01-01 | 새해 새 마음 | 빌립보서 3:13-14 | 새해 다짐 |
| 03-01 | 삼일절 | 갈라디아서 5:1 | 자유와 독립 |
| 05-08 | 어버이날 | 출애굽기 20:12 |  |
| 06-06 | 현충일 | 요한복음 15:13 |  |
| 08-15 | 광복절 | 갈라디아서 5:1 |  |
| 10-09 | 한글날 | 시편 19:14 | 말의 능력 |
| 11-수 | 추수감사주일 | 시편 100:4 | (주의: 패턴은 MM-DD만 지원, 추수감사 등 변동일은 매년 직접 추가 필요) |
| 12-25 | 성탄절 | 누가복음 2:10-11 | 그리스도의 탄생 |

## pattern 형식

- `MM-DD` 고정 (예: `12-25`)
- 양력 기준
- 부활절·추수감사절 등 매년 변동일은 해당 연도에 직접 행 추가 (예: `04-05` 부활절 2026)

## suggested_refs

- 콤마(,) 로 구분된 ref 목록 (현재 build_schedule는 첫 번째만 사용)
- ref 형식: `책이름 장:절-절` 또는 `책이름 장`
- 예: `빌3:13-14, 사43:18-19`
```

- [ ] **Step 2: Create `docs/setup/04-deployment-checklist.md`**

```markdown
# 배포 & 첫 실행 체크리스트

각 항목을 순서대로 체크하세요.

## 1. 외부 계정 (Task 1 가이드 참조)
- [ ] X Developer 계정 승인 + 자격증명 4개 발급
- [ ] Google Cloud Service Account + JSON 키 발급
- [ ] Google Sheet 생성 + 3개 탭(`schedule`, `meaningful_days`, `config`) + Service Account 공유

## 2. Sheet 시드 데이터
- [ ] `config` 탭에 row 입력:
  - `timezone` / `Asia/Seoul`
  - `tweet_template` / `{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}`
  - `safety_margin_weight` / `270`
- [ ] `meaningful_days` 탭에 시드 입력 (Task 16의 03 가이드 참조)

## 3. 로컬 데이터 가져오기
- [ ] `data/bible_text.csv` 가져오기 (다른 PC에서)
- [ ] YouTube 채널 URL 메모

## 4. 로컬 1회성 작업
```bash
# YouTube 크롤링
python -m scripts.crawl_youtube --channel <YOUR_CHANNEL_URL>

# 환경변수 설정 (PowerShell 예)
$env:GOOGLE_SHEETS_CREDS = Get-Content bible-bot-creds.json -Raw
$env:GOOGLE_SHEET_ID = "your_sheet_id"

# 1년치 일정 생성 (먼저 dry-run으로 검증)
python -m scripts.build_schedule --year 2026 --dry-run
python -m scripts.build_schedule --year 2026
```

## 5. GitHub Secrets 등록
저장소 Settings → Secrets and variables → Actions → New repository secret:
- [ ] `GOOGLE_SHEETS_CREDS` (JSON 전체)
- [ ] `GOOGLE_SHEET_ID`
- [ ] `TWITTER_API_KEY`
- [ ] `TWITTER_API_SECRET`
- [ ] `TWITTER_ACCESS_TOKEN`
- [ ] `TWITTER_ACCESS_SECRET`

## 6. 첫 실행 (수동 트리거 with dry-run)
1. Repo Actions 탭 → "Daily Tweet" → "Run workflow"
2. `dry_run: true`, `target_date: 2026-04-30` (예시)
3. 로그에서 트윗 본문 확인

## 7. 첫 실제 발행 (수동)
1. 부계정으로 자격증명 만들었으면 부계정에 발행
2. `dry_run: false` 로 실행
3. 트위터에서 실제 트윗 확인
4. Sheet의 `posted_at`, `tweet_id` 자동 업데이트 확인

## 8. 본 계정 전환
- [ ] X Developer App을 본 계정에 옮김 (또는 본 계정으로 새 자격증명 발급 + Secret 갱신)

## 9. cron 활성화
- 코드를 main 브랜치에 push하면 cron 자동 활성화 (별도 작업 불필요)
- 매일 06:00 KST (UTC 21:00 전날) 실행
- 실패 시 GitHub이 저장소 소유자 이메일로 알림

## 10. 첫 1주일 모니터링
매일:
- [ ] 본 계정에 트윗 올라온 것 확인
- [ ] Sheet의 `error` 컬럼 빈 칸인지 확인
- [ ] Actions 탭에서 워크플로우 초록색 확인
```

- [ ] **Step 3: Commit**

```bash
git add docs/setup/03-seed-meaningful-days.md docs/setup/04-deployment-checklist.md
git commit -m "docs: meaningful days seed and deployment checklist"
```

---

## Final Verification

- [ ] **All tests pass**

Run: `pytest -v`
Expected: All tests green (~50 tests across 9 test files).

- [ ] **Spec coverage check**

각 spec 섹션이 task로 구현되었는지 확인:
- §3 Key Decisions → Task 5,6,12,13,14에 분산 구현
- §4 Architecture → Task 2 (스캐폴딩) + 후속 task로 채움
- §5 Data Schema → Task 9 (sheets_client) + Task 13/14 (build)
- §6 Tweet Composition → Task 4,5,6,7
- §7 Module Responsibilities → Task 8~14에 1:1 매핑
- §8 Error Handling → Task 8 (retry, duplicate), Task 10 (멱등성, error 기록)
- §9 Test Strategy → 모든 task의 단위 테스트
- §10 Implementation Order → 본 plan과 일치 (risk-first)

- [ ] **Final commit / status check**

Run: `git log --oneline`
Expected: ~16개 커밋 깔끔하게 적재됨.

---

## Deferred Tasks (사용자 데이터 도착 후)

다음은 사용자가 다른 PC에서 데이터를 가져오고 외부 계정 셋업을 완료한 뒤에야 검증 가능:

- **Manual: YouTube 크롤러 실제 실행** — 채널 URL 필요
- **Manual: bible_text.csv 가져와서 build_schedule 실제 실행** — 본문 데이터 필요
- **Manual: X Developer 자격증명으로 첫 실 트윗** — 승인 후 가능
- **Manual: GitHub Actions workflow_dispatch 첫 트리거** — 위 셋업 완료 후
