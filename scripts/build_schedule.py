"""1년치 일정 생성 → Google Sheets에 업로드.

Usage:
    python -m scripts.build_schedule --year 2026
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta
from typing import Iterator


def generate_dates_for_year(year: int) -> Iterator[date]:
    """1월 1일부터 12월 31일까지의 모든 날짜."""
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        yield d
        d += timedelta(days=1)


def psalms_proverbs_cycle() -> list[tuple[str, int]]:
    """시편 1편 ~ 시편 150편, 잠언 1장 ~ 잠언 31장 = 총 181개."""
    cycle: list[tuple[str, int]] = []
    for ch in range(1, 151):
        cycle.append(("시편", ch))
    for ch in range(1, 32):
        cycle.append(("잠언", ch))
    return cycle


_CYCLE_CACHE: list[tuple[str, int]] | None = None


def cycle_ref_for_day_index(day_index: int) -> str:
    """day_index 0-based로 순환에서 ref 반환 (예: '시편 1', '잠언 5')."""
    global _CYCLE_CACHE
    if _CYCLE_CACHE is None:
        _CYCLE_CACHE = psalms_proverbs_cycle()
    book, chapter = _CYCLE_CACHE[day_index % len(_CYCLE_CACHE)]
    return f"{book} {chapter}"
