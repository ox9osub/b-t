"""Tests for scripts.build_verse_timestamps."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts import build_verse_timestamps as bvt


def test_format_hms_zero():
    assert bvt.format_hms(0.0) == "00:00:00"


def test_format_hms_truncates_fractional():
    assert bvt.format_hms(83.7) == "00:01:23"


def test_format_hms_one_hour_one_minute_one_second():
    assert bvt.format_hms(3661.0) == "01:01:01"


def test_format_hms_overflow_24h_does_not_wrap():
    # Bible book videos can exceed 5h but never 24h; format must still be sensible.
    assert bvt.format_hms(36_000.0) == "10:00:00"


def test_build_url_with_time_basic():
    url = bvt.build_url_with_time("https://youtu.be/abc", 83.456)
    assert url == "https://youtu.be/abc?t=83"


def test_build_url_with_time_zero():
    url = bvt.build_url_with_time("https://youtu.be/abc", 0.0)
    assert url == "https://youtu.be/abc?t=0"


def test_build_url_with_time_existing_query_param():
    url = bvt.build_url_with_time("https://youtu.be/abc?si=foo", 12.0)
    assert url == "https://youtu.be/abc?si=foo&t=12"


def test_build_url_without_time_returns_url_unchanged():
    """When start time is None (missing), return URL with no jump param."""
    assert bvt.build_url_with_time("https://youtu.be/abc", None) == "https://youtu.be/abc"
