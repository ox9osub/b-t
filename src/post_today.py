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
