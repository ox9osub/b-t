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
