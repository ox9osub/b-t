"""Twitter API v2 wrapper around tweepy."""
from __future__ import annotations
import time
import logging
from typing import Optional

import tweepy

log = logging.getLogger(__name__)


def _log_api_error(label: str, e: tweepy.errors.TweepyException) -> None:
    """Twitter API 에러의 모든 디테일을 로그로. 권한/인증 진단용."""
    log.error("=== %s 상세 ===", label)
    log.error("  api_codes    : %s", getattr(e, "api_codes", None))
    log.error("  api_messages : %s", getattr(e, "api_messages", None))
    log.error("  api_errors   : %s", getattr(e, "api_errors", None))
    resp = getattr(e, "response", None)
    if resp is not None:
        log.error("  status_code  : %s", getattr(resp, "status_code", None))
        try:
            log.error("  response.text: %s", resp.text)
        except Exception:
            pass
        try:
            log.error("  response.headers: %s", dict(resp.headers))
        except Exception:
            pass
    log.error("=== %s 끝 ===", label)


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
                _log_api_error("Forbidden", e)
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
