"""Upload data/bible_text.csv to a `bible_text` tab in the configured Google Sheet.

Reads the CSV produced by `scripts.build_verse_timestamps`, then uses
`SheetsClient.write_bible_text` to overwrite the sheet tab. Creates the tab
if missing.

Usage:
    GOOGLE_SHEETS_CREDS=$(cat bible-bot-creds.json) \
    GOOGLE_SHEET_ID=... \
    python -m scripts.upload_bible_text
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

from src.lib.sheets_client import SheetsClient

BIBLE_TEXT_CSV = Path("data/bible_text.csv")


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    return rows


def main() -> None:
    creds_raw = os.environ.get("GOOGLE_SHEETS_CREDS")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not creds_raw or not sheet_id:
        raise SystemExit("Set GOOGLE_SHEETS_CREDS and GOOGLE_SHEET_ID env vars.")
    if not BIBLE_TEXT_CSV.exists():
        raise SystemExit(f"{BIBLE_TEXT_CSV} not found; run build_verse_timestamps first.")

    rows = load_rows(BIBLE_TEXT_CSV)
    print(f"loaded {len(rows)} rows from {BIBLE_TEXT_CSV}", file=sys.stderr)

    client = SheetsClient(json.loads(creds_raw), sheet_id)
    client.write_bible_text(rows)
    print(f"uploaded {len(rows)} rows to bible_text tab", file=sys.stderr)


if __name__ == "__main__":
    main()
