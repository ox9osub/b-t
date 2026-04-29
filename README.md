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
