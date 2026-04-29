# Bible Twitter Bot — Design Spec

- **Date**: 2026-04-29
- **Status**: Draft (awaiting user review)
- **Owner**: ai3@int2.us

## 1. Purpose

매일 정해진 시간(KST 06:00)에 트위터(X)로 성경 본문 + 본문 낭독 YouTube 링크를 자동 포스팅하는 시스템.

- **평일**: 시편/잠언 순환에서 자동 배정된 짧은 본문
- **의미있는 날** (예: 1월 1일 새해, 3월 1일 삼일절, 부활절 등): 그 날의 의미에 맞춰 사전 큐레이션한 본문

## 2. Goals / Non-goals

### Goals
- 1년치 발행 일정을 미리 만들어두고, 매일 자동으로 해당 날짜 콘텐츠 발행
- 사용자가 일정을 어디서든(모바일 포함) 쉽게 편집
- 운영 비용 0원 (트위터 Free + GitHub Actions + Google Sheets 무료 등급)
- 실패 시 즉시 인지 가능 (조용한 실패 방지)
- 멱등성: 재실행/수동 트리거에도 중복 발행 없음

### Non-goals (v1)
- 자동 본문 선정 AI / LLM 활용
- 구절 단위 음성 영상 자동 제작·업로드
- 웹 UI (Google Sheets가 편집 인터페이스)
- 다국어, 다중 계정
- Discord/Slack 알림 (이메일로 시작)
- 분석 대시보드

## 3. Key Decisions

| 항목 | 결정 | 비고 |
|---|---|---|
| 콘텐츠 준비 모델 | 1년치 사전 생성 (의미있는 날=수동, 평일=자동 배정) | C 방식 |
| 평일 본문 선정 알고리즘 | 시편 150편 + 잠언 31장 순환 | E + C 조합 |
| 발행 시각 | 매일 KST 06:00 (cron `0 21 * * *` UTC) | GitHub Actions cron 5~30분 지연 가능 |
| 음성 단위 (v1) | 장(chapter) 단위 — 본인 채널 기존 영상 그대로 활용 | 데이터 스키마는 B/C/D로 확장 가능하게 유지 |
| 성경 번역본 | 본인이 가진 텍스트 파일에 맞춤 (음성과 일치) | 텍스트 가져온 뒤 확정 |
| 실행 환경 | GitHub Actions (cron + workflow_dispatch) | 무료 등급으로 충분 |
| 데이터 원천 (운영) | Google Sheets | 모바일/PC 어디서든 편집 |
| 데이터 원천 (참조) | 로컬 CSV (저장소 내) | 큰 데이터, 편집 안 함 |
| 트위터 API | Free 등급 | 월 30~50건 발행, 한도 500건 대비 충분 |
| 긴 본문 처리 | A + B 동시 도입 (빌드 단계 검증 + 운영 단계 자동 스레드) | 절 경계 분할, 첫 트윗에 YouTube URL |
| 언어/런타임 | Python 3.11+ | tweepy, gspread, yt-dlp |

## 4. Architecture

### 4.1 시스템 구성도

```
┌─────────────────────────────────────────────────────────┐
│  [1회성 준비 단계 — 로컬에서 실행]                         │
│                                                          │
│  ① crawl_youtube.py                                     │
│     본인 채널 → "책+장 → URL" 매핑 CSV 생성              │
│                                                          │
│  ② build_schedule.py                                    │
│     bible_text.csv + youtube_videos.csv +               │
│     Sheet의 meaningful_days + config                    │
│     → Sheet의 schedule 탭 1년치 자동 채우기              │
│                                                          │
│  ③ 사용자가 Sheet에서 의미있는 날 본문 손수 다듬기       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  [매일 운영 단계 — GitHub Actions]                        │
│                                                          │
│  매일 KST 06:00 cron 트리거 (UTC 21:00)                  │
│       │                                                  │
│       ▼                                                  │
│  post_today.py                                          │
│   1. Google Sheets에서 오늘 행 읽기                      │
│   2. 멱등성 체크 (tweet_id 있으면 종료)                  │
│   3. 트윗 본문 조립 (단일 또는 스레드)                   │
│   4. 트위터 API로 발행                                   │
│   5. Sheet의 posted_at + tweet_id 업데이트               │
│   6. 실패 시 error 컬럼 기록 + Action 빨강               │
└─────────────────────────────────────────────────────────┘
```

### 4.2 디렉토리 구조

```
b-t/
├── scripts/                 # 1회성/주기적 준비 (로컬 실행)
│   ├── crawl_youtube.py
│   └── build_schedule.py
├── src/                     # 매일 실행 (GitHub Actions)
│   ├── post_today.py
│   └── lib/
│       ├── sheets_client.py
│       ├── twitter_client.py
│       ├── tweet_builder.py
│       └── models.py
├── data/
│   ├── bible_text.csv       # 가져올 파일 (book, chapter, verse, text)
│   └── youtube_videos.csv   # crawl_youtube.py 출력
├── tests/
│   ├── test_tweet_builder.py
│   ├── test_build_schedule.py
│   └── test_post_today.py
├── docs/
│   └── superpowers/specs/
├── .github/workflows/
│   └── daily-post.yml
├── requirements.txt
└── README.md
```

### 4.3 의존성

```
tweepy>=4.14
gspread>=6.0
yt-dlp>=2024.0
python-dateutil>=2.8
```

## 5. Data Schema

### 5.1 Google Sheet (운영단계 — 편집 인터페이스)

**Tab `schedule`** (메인. 매일 cron이 읽음)

| 컬럼 | 타입 | 예시 | 설명 |
|---|---|---|---|
| `date` | date (KST) | `2026-01-01` | 발행 예정 날짜 |
| `day_kind` | enum | `meaningful` / `regular` | 의미있는 날 / 평일 |
| `label` | string | `새해 새 마음` | 의미있는 날 이름 (regular는 빈 값) |
| `bible_ref` | string | `빌립보서 3:13-14` | 본문 출처 표기 |
| `bible_text` | string | `형제들아 나는 아직...` | 트윗에 들어갈 본문 |
| `youtube_url` | string | `https://youtu.be/abc123` | 음성 링크 |
| `char_count` | int | `185` | 빌드 시 계산. 270 초과면 셀 빨강 |
| `needs_thread` | bool | `FALSE` | 빌드 시 자동 설정 (280 초과 = TRUE) |
| `posted_at` | datetime (UTC) | (자동) | 발행 완료 시각 |
| `tweet_id` | string | (자동) | 발행된 트윗 ID — 멱등성 체크 키 |
| `error` | string | (자동) | 실패 시 사유 |

**Tab `meaningful_days`** (의미있는 날 정의)

| 컬럼 | 예시 |
|---|---|
| `pattern` | `01-01`, `03-01`, `12-25` (MM-DD) |
| `name` | `새해 새 마음` |
| `suggested_refs` | `빌3:13-14, 사43:18-19` (콤마 구분) |
| `note` | (큐레이션 메모) |

**Tab `config`** (설정값)

| key | value |
|---|---|
| `timezone` | `Asia/Seoul` |
| `tweet_template` | `{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}` |
| `safety_margin_weight` | `270` |

> **주의**: Sheet 셀에 `\n` 을 입력하면 리터럴 백슬래시-n으로 저장됩니다. `tweet_builder` 가 읽을 때 `replace("\\n", "\n")` 으로 변환해서 실제 줄바꿈으로 처리합니다. (사용자가 셀 안에서 Alt+Enter로 입력해도 동작하도록 양쪽 케이스 모두 지원)

### 5.2 로컬 파일 (저장소 안 — 빌드 단계만 사용)

**`data/bible_text.csv`** — 성경 본문 전체 (사용자가 가져올 파일)
```
book,chapter,verse,text
창세기,1,1,태초에 하나님이 천지를 창조하시니라
...
```

**`data/youtube_videos.csv`** — `crawl_youtube.py` 출력
```
book,chapter,video_id,video_url,title
창세기,1,abc123,https://youtu.be/abc123,창세기 1장
...
```

### 5.3 데이터 분류 원칙

> **편집해야 하는 것 → Sheet, 큰 참조 데이터 → 로컬**

- 사용자가 직접 편집 (자주/가끔): Sheet
- 한 번 입력하고 안 건드림 + 크기 큼: 로컬 CSV
- Sheets API 호출 횟수/속도 측면에서도 유리

## 6. Tweet Composition

### 6.1 단일 트윗 (280 weighted units 이내)

`tweet_template` 적용 결과:

```
복 있는 사람은 악인들의 꾀를 따르지 아니하며
죄인들의 길에 서지 아니하며
오만한 자들의 자리에 앉지 아니하고

— 시편 1:1

🎧 https://youtu.be/abc123
```

**중요: 트위터의 글자수 계산 규칙 (twitter-text 라이브러리 기준)**
- **한글(Hangul) 1자 = 2 weight** (CJK 가중치)
- **이모지 1자 = 2 weight**
- **영문/숫자/일반 punctuation = 1 weight**
- **URL = 항상 23 weight** (실제 길이 무관, t.co로 자동 단축)
- **최대 = 280 weighted units**

→ 한글 위주 트윗의 실효 한도: 약 **120~130 한글 글자** (URL + 출처 표기 포함 시)

**안전 마진**: `safety_margin_weight = 270` (10 weight buffer for 가산 오차)

### 6.2 스레드 (280자 초과)

긴 본문은 **절(verse) 경계**로 자동 분할 → reply chain으로 연결.

```
[Tweet 1/3]
{본문 일부}

— 시편 1:1-3
🎧 https://youtu.be/abc123       ← 첫 트윗에만 URL (카드 미리보기)
       ↓ in_reply_to
[Tweet 2/3]
{본문 계속}
       ↓ in_reply_to
[Tweet 3/3]
{본문 마지막}
```

### 6.3 분할 우선순위
1. 절(verse) 경계
2. 문장 경계 (마침표, 느낌표, 물음표)
3. 어절 경계 (공백)
4. 마지막 수단: 글자 단위 (마커 `…` 추가)

각 트윗 끝에 `(N/총)` 표기.

## 7. Module Responsibilities

### 7.1 준비 단계 (로컬 실행)

#### `scripts/crawl_youtube.py`
- **입력**: 본인 채널 URL (또는 재생목록)
- **출력**: `data/youtube_videos.csv`
- **로직**: yt-dlp로 채널 메타 수집 → 제목 파싱 ("창세기 1장" → book="창세기", chapter=1) → CSV 저장
- **실행 시기**: 채널 업데이트 시

#### `scripts/build_schedule.py`
- **입력**: `bible_text.csv`, `youtube_videos.csv`, Sheet `meaningful_days` + `config`, `--year 2026`
- **출력**: Sheet `schedule` 탭 365행
- **로직**:
  1. 1월 1일 ~ 12월 31일 날짜 생성 (윤년 처리)
  2. 각 날짜에 대해:
     - `meaningful_days.pattern` 매칭 → `day_kind=meaningful`, 지정 ref 사용
     - 미매칭 → 시편/잠언 순환 알고리즘으로 ref 배정 (`day_kind=regular`)
  3. ref로 `bible_text.csv` 조회 → `bible_text` 채움
  4. ref의 책+장으로 `youtube_videos.csv` 조회 → `youtube_url` 채움
  5. tweet_template 적용 후 글자수 계산 → `char_count`, `needs_thread`
  6. Sheet에 일괄 업로드 (`gspread.update`)
- **실행 시기**: 연 1회 (12월에 다음해 일정 생성)
- **종료 시 출력 예시**:
  ```
  Built 2026 schedule:
    ✅ 365 entries written to Sheet
    📅 47 meaningful days, 318 regular days
    🧵 12 entries marked needs_thread (over 280 chars)
    ⚠️  3 chapters not found in youtube_videos.csv:
          - 요한계시록 22
          - 시편 119
          - 마가복음 8
  ```

### 7.2 운영 단계 (GitHub Actions)

#### `src/post_today.py`
- **입력**: 환경변수 (Sheet creds, Twitter creds), 옵션 `--dry-run --date YYYY-MM-DD`
- **출력**: 트윗 발행 + Sheet 업데이트
- **로직**:
  1. KST 오늘 날짜 계산 (`zoneinfo.ZoneInfo("Asia/Seoul")`)
  2. Sheet `schedule` 에서 오늘 행 조회
  3. **멱등성 체크**: `tweet_id` 있으면 즉시 종료
  4. `tweet_builder.build(row)` → 1개 또는 N개 텍스트
  5. `twitter_client.post_thread(texts)` → tweet_id 리스트
  6. Sheet `posted_at` + `tweet_id` 업데이트
  7. 예외 시 `error` 컬럼 기록 + Action 빨강

#### `src/lib/sheets_client.py`
- gspread 래퍼
- 주요 메서드: `get_today_row()`, `update_row(date, **fields)`, `get_meaningful_days()`, `get_config()`

#### `src/lib/twitter_client.py`
- tweepy 래퍼
- 주요 메서드: `post_tweet(text) -> tweet_id`, `post_thread(texts) -> List[tweet_id]`
- 지수 백오프 (1초→2초→4초, 3회)

#### `src/lib/tweet_builder.py`
- 순수 로직 (외부 의존성 0)
- 주요 메서드: `build(entry: ScheduleEntry, template: str, max_chars: int) -> List[str]`
- 단일/스레드 결정, 분할, `(N/총)` 표기

#### `src/lib/models.py`
- `ScheduleEntry` dataclass
- 시트 한 행을 표현

### 7.3 GitHub Actions Workflow

`.github/workflows/daily-post.yml`:
```yaml
on:
  schedule:
    - cron: '0 21 * * *'   # UTC 21:00 = KST 06:00 (다음날)
  workflow_dispatch:        # 수동 트리거 (테스트용)

jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m src.post_today
        env:
          GOOGLE_SHEETS_CREDS:    ${{ secrets.GOOGLE_SHEETS_CREDS }}
          GOOGLE_SHEET_ID:        ${{ secrets.GOOGLE_SHEET_ID }}
          TWITTER_API_KEY:        ${{ secrets.TWITTER_API_KEY }}
          TWITTER_API_SECRET:     ${{ secrets.TWITTER_API_SECRET }}
          TWITTER_ACCESS_TOKEN:   ${{ secrets.TWITTER_ACCESS_TOKEN }}
          TWITTER_ACCESS_SECRET:  ${{ secrets.TWITTER_ACCESS_SECRET }}
```

## 8. Error Handling & Observability

### 8.1 실패 시나리오 매트릭스

| 시나리오 | 발생 가능성 | 대응 |
|---|---|---|
| Twitter API 일시 장애 | 낮음 | 3회 지수 백오프 후 실패 |
| Google Sheets API 장애 | 매우 낮음 | 동일 retry, 실패 시 Action 빨강 |
| Twitter 인증 만료 | 가끔 | 명확한 에러 메시지 |
| 오늘 행이 시트에 없음 | 사용자 실수 | 명확한 에러 + Action 빨강 |
| `bible_text` 비어있음 | 사용자 실수 | 발행 중단 + Sheet `error` 기록 |
| 트윗 280자 초과 (스레드 미설정) | 본문 즉석 변경 시 | 발행 직전 재검증 → 자동 스레드 |
| 이미 오늘 발행했는데 재실행 | 수동 트리거 시 흔함 | `tweet_id` 체크 → 즉시 종료 |
| 발행 성공 후 Sheet 쓰기 실패 | 매우 드묾 | Twitter 자체 중복 방지가 다음 재시도 차단 |

### 8.2 멱등성

- **체크 키**: `tweet_id` 컬럼 존재 여부
- 발행 직후 즉시 Sheet 업데이트
- 만에 하나 발행 후 Sheet 쓰기 실패 시: Twitter 자체 중복 감지(에러 187)가 안전망

### 8.3 알림 채널 (단계적)

1. **GitHub Actions 자동 이메일** — workflow 실패 시 저장소 소유자에게 자동 발송 (별도 설정 0)
2. **Sheet `error` 컬럼** — 어떤 행에서 무엇이 잘못됐는지 가시화
3. **(추후) Discord/Slack 웹훅** — v1엔 미포함, 운영 중 필요 판단 시 추가

### 8.4 시간대 처리

| 사용처 | 시간대 |
|---|---|
| GitHub Actions cron | UTC |
| "오늘" 날짜 계산 | KST (`Asia/Seoul`) |
| `posted_at` 저장 | UTC ISO8601 |
| Sheet `date` 컬럼 | KST `YYYY-MM-DD` |

### 8.5 Dry-run 모드

```
python -m src.post_today --dry-run --date 2026-03-01
```
- 실제 발행 없이 트윗 본문 출력
- 의미있는 날 본문, 스레드 분할 검증용

## 9. Test Strategy

### 9.1 핵심 단위 테스트

**`test_tweet_builder.py`**
- 짧은 본문 → 단일 트윗
- 긴 본문 → 스레드 분할 + `(N/총)` 표기
- 절 경계에서 분할
- 한글 글자수 = 2 weight (CJK 가중치 — twitter-text 규칙)
- URL = 23 weight
- 첫 트윗에만 YouTube URL

**`test_build_schedule.py`**
- 윤년(2028) → 366일
- 의미있는 날 패턴 매칭
- 시편/잠언 순환이 빈 날짜 다 채움
- 누락된 참조는 명확한 에러로 보고

**`test_post_today.py`**
- `tweet_id` 있으면 즉시 종료 (idempotent)
- KST 기준 "오늘" 계산
- 실패 경로에서 `error` 기록

### 9.2 통합 테스트
- 별도 테스트 Google Sheet + 테스트 트위터 부계정
- CI 미포함 (로컬 수동), Twitter API 비용 절약

### 9.3 수동 검증
- `workflow_dispatch` 로 GitHub Actions 수동 트리거
- 실제 부계정에 발행 확인 후 본 계정 전환

## 10. Implementation Order (Risk-first)

각 단계는 **명확한 검증 액션**으로 완료 확인 후 다음으로 진행.

| Step | 작업 | 완료 기준 |
|---|---|---|
| 1 | 프로젝트 스캐폴딩 + models + tweet_builder + 단위테스트 | 단위 테스트 100% pass |
| 2 | ★ X Developer 계정 승인 + twitter_client + 실제 발행 테스트 | 부계정에 테스트 트윗 1건 발행됨 |
| 3 | Google Cloud + Service Account + sheets_client | 테스트 시트에 read/write 동작 |
| 4 | crawl_youtube.py + 본인 채널 1회 크롤링 | `youtube_videos.csv` 생성, 누락/오타 사용자 검증 |
| 5 | bible_text.csv 가져옴 + build_schedule.py + 2026 일정 생성 | Sheet 365행 채워짐, 사용자 큐레이션 |
| 6 | post_today.py + dry-run | 다양한 날짜 dry-run 정상 |
| 7 | GitHub Actions 배포 + Secrets 등록 + 수동 트리거 | workflow_dispatch로 실제 발행 |
| 8 | 운영 관찰 (1~2주) | 매일 정상 발행 + 에러 0 |

**Step 2를 가장 먼저 외부 의존성으로 검증** — X Developer 승인 거부 시 전체 계획 재검토가 필요하기 때문.

## 11. Out of Scope (v1)

- AI 자동 본문 선정
- 구절 단위 음성 영상 자동 제작/업로드
- 웹 UI
- 다국어, 다중 계정
- Discord/Slack 알림
- 분석 대시보드
- 음성 단위 옵션 B/C/D (장 단위로 시작, 데이터 스키마는 확장 가능하게 유지)

## 12. Open Questions (구현 단계에서 확정)

### 사용자가 다른 PC에서 데이터 가져온 후
- 성경 번역본 (개역개정 / 새번역 / 공동번역 / 기타) — 음성과 일치 필요
- `bible_text.csv` 정확한 컬럼 형식 (예상: `book, chapter, verse, text`)
- YouTube 채널 URL
- 의미있는 날 초기 목록 (사용자가 1회 작성)

### 구현 계획 단계에서 결정
- **시편/잠언 순환 알고리즘** — 다음 중 어떤 방식을 쓸지:
  - (a) 시편 1편 → 잠언 1장 → 시편 2편 → 잠언 2장 ... 교대
  - (b) 시편 150편 먼저 끝낸 후 잠언 31장
  - (c) 절(verse) 단위 분할 (시편 1:1 → 시편 1:2 ... 더 잘게)
  - 트윗 분량 적합도 + 큐레이션 자연스러움 기준으로 implementation plan 단계에서 선택
