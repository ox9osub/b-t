"""Seed `config` and `meaningful_days` tabs in Google Sheet (one-shot setup).

`meaningful_days` is derived from data/year_plan_<YEAR>.csv (rows where
day_kind == 'meaningful'). The `pattern` column for the Sheet is MM-DD,
extracted from the YYYY-MM-DD date column.

Usage:
    GOOGLE_SHEETS_CREDS=$(cat bible-bot-creds.json) \
    GOOGLE_SHEET_ID=your_sheet_id \
    python -m scripts.seed_sheet [--year 2026]
"""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path

from src.lib.sheets_client import SheetsClient


CONFIG_ITEMS: list[tuple[str, str]] = [
    ("timezone", "Asia/Seoul"),
    ("tweet_template", "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}\n\n#오늘의말씀 #말씀묵상 #성경듣기"),
    ("safety_margin_weight", "270"),
]


def load_meaningful_days_from_year_plan(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("day_kind") != "meaningful":
                continue
            d = r["date"]  # YYYY-MM-DD
            pattern = d[5:]  # MM-DD
            rows.append({
                "pattern": pattern,
                "name": r.get("label", ""),
                "suggested_refs": r.get("bible_ref", ""),
                "note": r.get("note", ""),
            })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--year-plan", type=Path, default=None,
                        help="Override year_plan CSV path")
    args = parser.parse_args()

    year_plan_path = args.year_plan or Path(f"data/year_plan_{args.year}.csv")
    if not year_plan_path.exists():
        raise SystemExit(f"Year plan CSV not found: {year_plan_path}")

    creds_raw = os.environ.get("GOOGLE_SHEETS_CREDS")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_raw or not sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID env vars.")

    meaningful_days = load_meaningful_days_from_year_plan(year_plan_path)

    client = SheetsClient(json.loads(creds_raw), sheet_id)
    client.write_config(CONFIG_ITEMS)
    print(f"config: {len(CONFIG_ITEMS)} rows written")
    client.write_meaningful_days(meaningful_days)
    print(f"meaningful_days: {len(meaningful_days)} rows written (from {year_plan_path.name})")


if __name__ == "__main__":
    main()
