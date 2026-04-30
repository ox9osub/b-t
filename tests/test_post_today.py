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


def test_duplicate_error_treated_as_skip():
    """Twitter error 187 (duplicate) means the tweet was already posted in a
    previous run; per spec §8.2 this is a safety net, not a failure."""
    sheets = MagicMock()
    sheets.get_row.return_value = make_entry()
    sheets.get_config.return_value = {"tweet_template": "{bible_text}"}
    twitter = MagicMock()
    twitter.post_thread.side_effect = DuplicateTweetError("dup")

    result = run_post(sheets, twitter, target_date=date(2026, 1, 1), dry_run=False)

    assert result["status"] == "skipped"
    assert result["reason"] == "duplicate"
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
