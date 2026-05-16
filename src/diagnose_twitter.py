"""Twitter API 권한/인증 진단 스크립트.

로컬에서 `keys` 파일의 자격증명으로 다음을 순서대로 확인:
  1. 자격증명 4종이 모두 로드되었는지 (마스킹된 값으로 표시)
  2. get_me() — 읽기 권한 + 인증된 계정 식별
  3. create_tweet() — 쓰기 권한 (실제로 짧은 테스트 트윗을 게시)
  4. delete_tweet() — 게시된 테스트 트윗 즉시 삭제 시도

사용:
    .\.venv\Scripts\python.exe -m src.diagnose_twitter
    .\.venv\Scripts\python.exe -m src.diagnose_twitter --no-post   # 쓰기 시도 생략
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import tweepy

log = logging.getLogger("diagnose")

KEYS_PATH = Path(__file__).resolve().parent.parent / "keys"


def load_keys_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def mask(s: str | None) -> str:
    if not s:
        return "<EMPTY>"
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}…{s[-4:]} (len={len(s)})"


def _dump_error(label: str, e: BaseException) -> None:
    log.error("--- %s: %s ---", label, type(e).__name__)
    log.error("  str(e)       : %s", e)
    for attr in ("api_codes", "api_messages", "api_errors"):
        if hasattr(e, attr):
            log.error("  %-13s: %s", attr, getattr(e, attr))
    resp = getattr(e, "response", None)
    if resp is not None:
        log.error("  status_code  : %s", getattr(resp, "status_code", None))
        try:
            log.error("  response.text: %s", resp.text)
        except Exception:
            pass
        try:
            log.error("  resp.headers : %s", dict(resp.headers))
        except Exception:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-post", action="store_true",
                        help="쓰기 테스트(트윗 게시) 생략, 읽기 검증만")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # tweepy 내부 로그도 보고 싶다면 활성화
    logging.getLogger("tweepy").setLevel(logging.DEBUG)
    logging.getLogger("oauthlib").setLevel(logging.DEBUG)
    logging.getLogger("requests_oauthlib").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.INFO)

    # 1) 자격증명 로드: env 우선, 없으면 keys 파일
    file_keys = load_keys_file(KEYS_PATH)
    def pick(name: str) -> str:
        return os.environ.get(name) or file_keys.get(name, "")

    api_key = pick("TWITTER_API_KEY")
    api_secret = pick("TWITTER_API_SECRET")
    access_token = pick("TWITTER_ACCESS_TOKEN")
    access_secret = pick("TWITTER_ACCESS_SECRET")

    log.info("=== Step 1: 자격증명 확인 ===")
    log.info("  source       : %s%s",
             "env" if os.environ.get("TWITTER_API_KEY") else "keys 파일",
             f" ({KEYS_PATH})" if not os.environ.get("TWITTER_API_KEY") else "")
    log.info("  api_key      : %s", mask(api_key))
    log.info("  api_secret   : %s", mask(api_secret))
    log.info("  access_token : %s", mask(access_token))
    log.info("  access_secret: %s", mask(access_secret))

    missing = [n for n, v in [
        ("TWITTER_API_KEY", api_key),
        ("TWITTER_API_SECRET", api_secret),
        ("TWITTER_ACCESS_TOKEN", access_token),
        ("TWITTER_ACCESS_SECRET", access_secret),
    ] if not v]
    if missing:
        log.error("누락된 자격증명: %s", missing)
        return 2

    # access_token은 보통 `<numeric_user_id>-<random>` 형식. user_id 부분 확인.
    if "-" in access_token:
        user_id_from_token = access_token.split("-", 1)[0]
        log.info("  access_token에서 추출한 user_id: %s", user_id_from_token)

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    # 2) get_me() — 인증된 계정 확인 (OAuth 1.0a 토큰 검증)
    log.info("=== Step 2: get_me() (읽기 권한 검증) ===")
    try:
        me = client.get_me(user_auth=True)
        if me.data:
            log.info("  ✓ 인증 OK — id=%s username=@%s name=%s",
                     me.data.id, me.data.username, me.data.name)
        else:
            log.warning("  응답에 data 없음: %s", me)
    except tweepy.errors.Unauthorized as e:
        _dump_error("Unauthorized in get_me", e)
        log.error("→ 토큰이 만료/무효. regenerate 후 keys 파일 갱신 필요.")
        return 1
    except tweepy.errors.Forbidden as e:
        _dump_error("Forbidden in get_me", e)
        log.error("→ 읽기조차 막힘. 앱이 suspended이거나 계정 제한 가능성.")
        return 1
    except Exception as e:
        _dump_error("Unexpected in get_me", e)
        return 1

    if args.no_post:
        log.info("--no-post 지정 → 쓰기 테스트 생략")
        return 0

    # 3) create_tweet() — 쓰기 권한 검증 (짧은 테스트 트윗)
    log.info("=== Step 3: create_tweet() (쓰기 권한 검증) ===")
    test_text = f"diagnostic test {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    log.info("  보낼 텍스트: %r (길이=%d)", test_text, len(test_text))
    try:
        resp = client.create_tweet(text=test_text, user_auth=True)
        tid = resp.data["id"]
        log.info("  ✓ 게시 성공 — tweet_id=%s", tid)
    except tweepy.errors.Forbidden as e:
        _dump_error("Forbidden in create_tweet", e)
        log.error("→ 쓰기 권한 없음. 다음 확인:")
        log.error("  • Developer Portal → App → User authentication settings → App permissions = 'Read and write' 이상")
        log.error("  • 권한 변경 *후* Access Token regenerate 했는지 (변경 전 토큰은 옛 권한 유지)")
        log.error("  • Project tier (Free)에서 월 post 한도 초과는 아닌지")
        log.error("  • get_me()에서 본 username이 실제 게시하려는 계정과 일치하는지")
        return 1
    except tweepy.errors.BadRequest as e:
        _dump_error("BadRequest in create_tweet", e)
        return 1
    except Exception as e:
        _dump_error("Unexpected in create_tweet", e)
        return 1

    # 4) 테스트 트윗 즉시 삭제
    log.info("=== Step 4: delete_tweet (테스트 트윗 정리) ===")
    try:
        client.delete_tweet(id=tid, user_auth=True)
        log.info("  ✓ 삭제 완료")
    except Exception as e:
        _dump_error("delete_tweet 실패 (수동 삭제 필요)", e)
        log.warning("→ tweet_id=%s 를 수동으로 삭제하세요", tid)

    log.info("=== 모든 검증 통과: 인증 OK + 읽기 OK + 쓰기 OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
