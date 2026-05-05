"""Refresh the `youtube_url` column in the `schedule` tab using current bible_text.csv.

Reads each row's bible_ref from the existing schedule, looks up the matching
per-verse URL in `data/bible_text.csv`, and updates only that column. Other
columns (posted_at, tweet_id, error history) are left untouched.

Usage:
    GOOGLE_SHEETS_CREDS=$(cat bible-bot-creds.json) \
    GOOGLE_SHEET_ID=... \
    python -m scripts.refresh_schedule_urls [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from scripts.build_schedule import load_bible_csv, load_youtube_csv, resolve_ref_text
from src.lib.models import BibleRef
from src.lib.sheets_client import SheetsClient

BIBLE_TEXT_CSV = Path("data/bible_text.csv")
YOUTUBE_VIDEOS_CSV = Path("data/youtube_videos.csv")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Compute new URLs but do not push to Sheet")
    args = p.parse_args()

    creds_raw = os.environ.get("GOOGLE_SHEETS_CREDS")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_raw or not sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID env vars.")

    bible = load_bible_csv(BIBLE_TEXT_CSV)
    yt = load_youtube_csv(YOUTUBE_VIDEOS_CSV)

    client = SheetsClient(json.loads(creds_raw), sheet_id)
    ws = client._ss.worksheet("schedule")
    records = ws.get_all_records()

    value_for_date: dict[str, str] = {}
    for rec in records:
        d = str(rec.get("date", ""))
        ref_str = str(rec.get("bible_ref", "") or "")
        if not d or not ref_str:
            continue
        _, _, verse_url = resolve_ref_text(bible, ref_str)
        url = verse_url
        if not url:
            try:
                ref = BibleRef.parse(ref_str)
                url = yt.get(ref.book, ref.chapter)
            except ValueError:
                url = ""
        value_for_date[d] = url

    print(f"loaded {len(records)} schedule rows; computed URLs for {len(value_for_date)} dates",
          file=sys.stderr)

    if args.dry_run:
        diffs = 0
        for rec in records:
            d = str(rec.get("date", ""))
            current = str(rec.get("youtube_url", "") or "")
            new = value_for_date.get(d, current)
            if new != current:
                diffs += 1
                if diffs <= 5:
                    print(f"  {d}: {current!r}  →  {new!r}", file=sys.stderr)
        print(f"dry-run: {diffs} rows would change (showed first 5)", file=sys.stderr)
        return

    changed = client.refresh_schedule_column("youtube_url", value_for_date)
    print(f"updated youtube_url for {changed} rows in schedule tab", file=sys.stderr)


if __name__ == "__main__":
    main()
