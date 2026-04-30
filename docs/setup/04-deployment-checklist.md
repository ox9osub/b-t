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
