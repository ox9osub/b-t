"""Google Sheets wrapper using gspread."""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Any

import gspread
from google.oauth2.service_account import Credentials

from src.lib.models import ScheduleEntry


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _empty_to_none(v: Any) -> Optional[str]:
    if v is None or v == "":
        return None
    return str(v)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class SheetsClient:
    def __init__(self, creds_dict: dict, sheet_id: str, _spreadsheet=None):
        # _spreadsheet allows test injection
        if _spreadsheet is not None:
            self._ss = _spreadsheet
        else:
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            client = gspread.authorize(creds)
            self._ss = client.open_by_key(sheet_id)

    def get_row(self, target_date: date) -> Optional[ScheduleEntry]:
        ws = self._ss.worksheet("schedule")
        records = ws.get_all_records()
        target_str = target_date.isoformat()
        for rec in records:
            if str(rec.get("date")) == target_str:
                return self._record_to_entry(rec)
        return None

    def update_row(self, target_date: date, **fields):
        ws = self._ss.worksheet("schedule")
        records = ws.get_all_records()
        header = ws.row_values(1)
        col_idx = {name: i + 1 for i, name in enumerate(header)}

        target_str = target_date.isoformat()
        row_num = None
        for i, rec in enumerate(records, start=2):  # row 1 is header
            if str(rec.get("date")) == target_str:
                row_num = i
                break
        if row_num is None:
            raise ValueError(f"No row for date {target_date}")

        for key, value in fields.items():
            if key not in col_idx:
                raise ValueError(f"Unknown column: {key}")
            if isinstance(value, datetime):
                value = value.isoformat()
            ws.update_cell(row_num, col_idx[key], str(value) if value is not None else "")

    def get_config(self) -> dict:
        ws = self._ss.worksheet("config")
        records = ws.get_all_records()
        return {r["key"]: r["value"] for r in records}

    def get_meaningful_days(self) -> list[dict]:
        ws = self._ss.worksheet("meaningful_days")
        return ws.get_all_records()

    def write_schedule_rows(self, rows: list[dict]):
        """Replace entire schedule tab with given rows. Used by build_schedule."""
        ws = self._ss.worksheet("schedule")
        if not rows:
            return
        header = list(rows[0].keys())
        values = [header] + [[str(r.get(h, "")) for h in header] for r in rows]
        ws.clear()
        ws.update("A1", values)

    def write_config(self, items: list[tuple[str, str]]):
        """Replace entire config tab with header + key/value rows."""
        ws = self._ss.worksheet("config")
        values = [["key", "value"]] + [[k, v] for k, v in items]
        ws.clear()
        ws.update("A1", values)

    def write_meaningful_days(self, rows: list[dict]):
        """Replace entire meaningful_days tab with header + rows."""
        ws = self._ss.worksheet("meaningful_days")
        header = ["pattern", "name", "suggested_refs", "note"]
        values = [header] + [[str(r.get(h, "")) for h in header] for r in rows]
        ws.clear()
        ws.update("A1", values)

    def refresh_schedule_column(self, column: str, value_for_date: dict[str, str]) -> int:
        """Overwrite a single column of the `schedule` tab in-place, preserving all
        other columns (e.g., posted_at, tweet_id history).

        `value_for_date` maps `YYYY-MM-DD` → new cell value. Rows whose date is not
        present in the mapping keep their existing value. Returns the count of
        rows actually changed.
        """
        ws = self._ss.worksheet("schedule")
        header = ws.row_values(1)
        if column not in header:
            raise ValueError(f"column {column!r} not in schedule header: {header}")
        col_idx = header.index(column)
        records = ws.get_all_records()
        col_letter = gspread.utils.rowcol_to_a1(1, col_idx + 1)[:-1]  # strip trailing "1"

        new_values: list[list[str]] = []
        changed = 0
        for rec in records:
            d = str(rec.get("date", ""))
            current = str(rec.get(column, "") or "")
            new = value_for_date.get(d, current)
            if new != current:
                changed += 1
            new_values.append([new])
        last_row = len(records) + 1  # +1 for header
        rng = f"{col_letter}2:{col_letter}{last_row}"
        ws.update(new_values, rng, value_input_option="RAW")
        return changed

    def write_bible_text(self, rows: list[dict], tab: str = "bible_text"):
        """Replace entire bible_text tab with header + rows.

        Creates the tab if it does not exist. Uses RAW value input so verse
        text containing leading "=" or "+" is not interpreted as a formula.
        """
        try:
            ws = self._ss.worksheet(tab)
        except gspread.WorksheetNotFound:
            ws = self._ss.add_worksheet(title=tab, rows=max(len(rows) + 1, 100), cols=10)
        header = ["book", "chapter", "verse", "text", "video_url", "start_seconds", "start_hms"]
        values = [header] + [[str(r.get(h, "")) for h in header] for r in rows]
        ws.clear()
        # value_input_option="RAW" prevents Sheets from auto-parsing strings
        # like "=foo" as formulas (matters for verse text starting with "=").
        ws.update(values, "A1", value_input_option="RAW")

    def _record_to_entry(self, rec: dict) -> ScheduleEntry:
        return ScheduleEntry(
            date=date.fromisoformat(str(rec["date"])),
            day_kind=str(rec.get("day_kind", "regular")),
            label=str(rec.get("label", "") or ""),
            bible_ref=str(rec.get("bible_ref", "")),
            bible_text=str(rec.get("bible_text", "")),
            youtube_url=str(rec.get("youtube_url", "")),
            char_count=int(rec.get("char_count") or 0),
            needs_thread=str(rec.get("needs_thread", "")).upper() == "TRUE",
            posted_at=_parse_dt(str(rec.get("posted_at", "") or "")),
            tweet_id=_empty_to_none(rec.get("tweet_id")),
            error=str(rec.get("error", "") or ""),
        )
