# 외부 서비스 셋업 가이드

이 봇은 외부 서비스 3개의 계정/인증이 필요합니다. 시간이 오래 걸리는 것부터 시작하세요.

## 셋업 순서 (병렬 가능)

1. [X (Twitter) Developer 계정](./01-x-developer-account.md) — **가장 먼저 시작**. 승인 대기 시간 발생 가능 (즉시~며칠)
2. [Google Cloud Service Account](./02-google-cloud-service-account.md) — 30분 정도 소요
3. YouTube 채널 — 본인 채널 URL만 메모해두면 됨 (계정 신청 불필요)

각 단계 완료 후 받은 자격증명은 **GitHub Secrets**에 저장합니다 (Step 5의 `daily-post.yml` 참조).
