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


from src.lib.models import BibleRef
from src.lib.tweet_builder import weighted_count


class BibleTextLookup:
    """{(book, chapter, verse): text} lookup."""
    def __init__(self, data: dict[tuple[str, int, int], str]):
        self._data = dict(data)

    def get(self, book: str, chapter: int, verse: int) -> str:
        return self._data.get((book, chapter, verse), "")

    def chapter_verses(self, book: str, chapter: int) -> list[tuple[int, str]]:
        """Return all (verse_num, text) for a chapter, sorted by verse_num."""
        items = [(v, t) for (b, c, v), t in self._data.items() if b == book and c == chapter]
        return sorted(items, key=lambda x: x[0])


class YoutubeUrlLookup:
    """{(book, chapter): url}"""
    def __init__(self, data: dict[tuple[str, int], str]):
        self._data = dict(data)

    def get(self, book: str, chapter: int) -> str:
        return self._data.get((book, chapter), "")


def match_meaningful_day(d: date, meaningful_days: list[dict]) -> dict | None:
    """Return matching meaningful day record or None."""
    pattern = d.strftime("%m-%d")
    for entry in meaningful_days:
        if str(entry.get("pattern", "")).strip() == pattern:
            return entry
    return None


def pick_first_n_verses(lookup: BibleTextLookup, book: str, chapter: int,
                         n: int = 3) -> tuple[str, str]:
    """Return (ref_string, joined_text) for first N verses of a chapter."""
    verses = lookup.chapter_verses(book, chapter)
    if not verses:
        return f"{book} {chapter}", ""
    selected = verses[:n]
    texts = [t for _, t in selected]
    if len(selected) == 1:
        ref = f"{book} {chapter}:{selected[0][0]}"
    else:
        ref = f"{book} {chapter}:{selected[0][0]}-{selected[-1][0]}"
    return ref, "\n".join(texts)


def parse_suggested_refs(s: str) -> list[str]:
    """Comma-separated refs from sheet → list, picks first."""
    return [r.strip() for r in str(s or "").split(",") if r.strip()]


def resolve_meaningful_text(lookup: BibleTextLookup, ref_str: str) -> tuple[str, str]:
    """Given a ref string like '빌립보서 3:13-14', return (formatted_ref, joined_text)."""
    try:
        ref = BibleRef.parse(ref_str)
    except ValueError:
        return ref_str, ""
    if ref.verse_start is None:
        # Whole chapter — pick first 3 verses
        return pick_first_n_verses(lookup, ref.book, ref.chapter, n=3)
    texts = []
    for v in range(ref.verse_start, (ref.verse_end or ref.verse_start) + 1):
        t = lookup.get(ref.book, ref.chapter, v)
        if t:
            texts.append(t)
    return ref.format(), "\n".join(texts)


class ScheduleBuilder:
    def __init__(self, bible: BibleTextLookup, youtube: YoutubeUrlLookup,
                 meaningful_days: list[dict], template: str):
        self.bible = bible
        self.youtube = youtube
        self.meaningful_days = meaningful_days
        self.template = template
        self.summary = {
            "total": 0,
            "meaningful": 0,
            "regular": 0,
            "needs_thread": 0,
            "missing_youtube": [],
            "missing_text": [],
        }

    def build_year(self, year: int) -> list[dict]:
        rows: list[dict] = []
        regular_index = 0
        for d in generate_dates_for_year(year):
            mday = match_meaningful_day(d, self.meaningful_days)
            if mday:
                refs = parse_suggested_refs(mday.get("suggested_refs", ""))
                ref_str = refs[0] if refs else ""
                ref_formatted, text = resolve_meaningful_text(self.bible, ref_str) if ref_str else ("", "")
                row = self._make_row(d, "meaningful", str(mday.get("name", "")),
                                      ref_formatted, text)
                self.summary["meaningful"] += 1
            else:
                ref_str = cycle_ref_for_day_index(regular_index)
                ref = BibleRef.parse(ref_str)
                ref_formatted, text = pick_first_n_verses(self.bible, ref.book, ref.chapter, n=3)
                row = self._make_row(d, "regular", "", ref_formatted, text)
                self.summary["regular"] += 1
                regular_index += 1
            rows.append(row)
            self.summary["total"] += 1
        return rows

    def _make_row(self, d: date, day_kind: str, label: str,
                  bible_ref: str, bible_text: str) -> dict:
        # Lookup youtube URL (parse book/chapter from ref)
        try:
            ref = BibleRef.parse(bible_ref)
            url = self.youtube.get(ref.book, ref.chapter)
            if not url:
                self.summary["missing_youtube"].append(f"{ref.book} {ref.chapter}")
        except ValueError:
            url = ""
        if not bible_text:
            self.summary["missing_text"].append(bible_ref)

        # Compute char_count by simulating template render
        rendered = self.template.replace("\\n", "\n").format(
            bible_text=bible_text, bible_ref=bible_ref,
            youtube_url=url, label=label,
        )
        cc = weighted_count(rendered)
        needs_thread = cc > 280
        if needs_thread:
            self.summary["needs_thread"] += 1

        return {
            "date": d.isoformat(),
            "day_kind": day_kind,
            "label": label,
            "bible_ref": bible_ref,
            "bible_text": bible_text,
            "youtube_url": url,
            "char_count": cc,
            "needs_thread": "TRUE" if needs_thread else "FALSE",
            "posted_at": "",
            "tweet_id": "",
            "error": "",
        }
