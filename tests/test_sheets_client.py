from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from src.lib.sheets_client import SheetsClient
from src.lib.models import ScheduleEntry


def make_client(mock_spreadsheet):
    return SheetsClient(creds_dict={}, sheet_id="x", _spreadsheet=mock_spreadsheet)


def test_get_today_row_returns_entry():
    # Mock the schedule worksheet's records
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {
            "date": "2026-01-01", "day_kind": "meaningful",
            "label": "새해 새 마음", "bible_ref": "빌립보서 3:13-14",
            "bible_text": "형제들아", "youtube_url": "https://youtu.be/abc",
            "char_count": 100, "needs_thread": "FALSE",
            "posted_at": "", "tweet_id": "", "error": "",
        },
        {
            "date": "2026-01-02", "day_kind": "regular",
            "label": "", "bible_ref": "시편 1:1",
            "bible_text": "복 있는 사람은", "youtube_url": "https://youtu.be/xyz",
            "char_count": 50, "needs_thread": "FALSE",
            "posted_at": "", "tweet_id": "", "error": "",
        },
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)

    entry = c.get_row(date(2026, 1, 2))
    assert entry is not None
    assert entry.bible_ref == "시편 1:1"
    assert entry.day_kind == "regular"
    assert entry.tweet_id is None  # Empty string converted to None


def test_get_today_row_missing_returns_none():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = []
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)
    assert c.get_row(date(2026, 1, 1)) is None


def test_update_row_writes_correct_cells():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {"date": "2026-01-01", "day_kind": "regular", "label": "",
         "bible_ref": "x", "bible_text": "y", "youtube_url": "z",
         "char_count": 0, "needs_thread": "FALSE",
         "posted_at": "", "tweet_id": "", "error": ""}
    ]
    # Header row (1) + first data row (2)
    mock_ws.row_values.return_value = [
        "date", "day_kind", "label", "bible_ref", "bible_text",
        "youtube_url", "char_count", "needs_thread",
        "posted_at", "tweet_id", "error"
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)

    posted_at = datetime(2026, 1, 1, 21, 0, 0, tzinfo=timezone.utc)
    c.update_row(date(2026, 1, 1), posted_at=posted_at, tweet_id="9999")

    # Verify update_cell was called for posted_at and tweet_id columns
    calls = mock_ws.update_cell.call_args_list
    # row index = 2 (header is 1), columns: posted_at=9, tweet_id=10
    assert (2, 9, posted_at.isoformat()) in [c.args for c in calls]
    assert (2, 10, "9999") in [c.args for c in calls]


def test_get_config_returns_dict():
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = [
        {"key": "timezone", "value": "Asia/Seoul"},
        {"key": "tweet_template", "value": "{bible_text}\\n— {bible_ref}"},
    ]
    mock_ss = MagicMock()
    mock_ss.worksheet.return_value = mock_ws
    c = make_client(mock_ss)
    config = c.get_config()
    assert config["timezone"] == "Asia/Seoul"
    assert "{bible_text}" in config["tweet_template"]
