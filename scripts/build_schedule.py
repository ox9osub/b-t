"""1년치 일정 생성 → Google Sheets에 업로드.

매일의 ref/label/day_kind는 data/year_plan_<YEAR>.csv 에서 옴 (사람이 큐레이션).
본문 텍스트는 data/bible_text.csv 에서, YouTube URL은 data/youtube_videos.csv 에서 룩업.

Usage:
    python -m scripts.build_schedule --year 2026
"""
from __future__ import annotations
import argparse
import csv as _csv
import json as _json
import os
from datetime import date
from pathlib import Path

from src.lib.models import BibleRef
from src.lib.tweet_builder import weighted_count


class BibleTextLookup:
    """{(book, chapter, verse): text} + optional per-verse YouTube URL with timestamp."""
    def __init__(self,
                 data: dict[tuple[str, int, int], str],
                 url_data: dict[tuple[str, int, int], str] | None = None):
        self._data = dict(data)
        self._urls = dict(url_data or {})

    def get(self, book: str, chapter: int, verse: int) -> str:
        return self._data.get((book, chapter, verse), "")

    def get_url(self, book: str, chapter: int, verse: int) -> str:
        return self._urls.get((book, chapter, verse), "")

    def chapter_verses(self, book: str, chapter: int) -> list[tuple[int, str]]:
        items = [(v, t) for (b, c, v), t in self._data.items() if b == book and c == chapter]
        return sorted(items, key=lambda x: x[0])


class YoutubeUrlLookup:
    """{(book, chapter): url}. Falls back to (book, 0) whole-book audio when
    a chapter-specific URL is missing."""
    def __init__(self, data: dict[tuple[str, int], str]):
        self._data = dict(data)

    def get(self, book: str, chapter: int) -> str:
        url = self._data.get((book, chapter), "")
        if url:
            return url
        return self._data.get((book, 0), "")


def pick_first_n_verses(lookup: BibleTextLookup, book: str, chapter: int,
                         n: int = 3) -> tuple[str, str, str]:
    """For whole-chapter refs: first N verses, joined. Returns (ref, text, first_verse_url)."""
    verses = lookup.chapter_verses(book, chapter)
    if not verses:
        return f"{book} {chapter}", "", ""
    selected = verses[:n]
    texts = [t for _, t in selected]
    if len(selected) == 1:
        ref = f"{book} {chapter}:{selected[0][0]}"
    else:
        ref = f"{book} {chapter}:{selected[0][0]}-{selected[-1][0]}"
    first_verse_url = lookup.get_url(book, chapter, selected[0][0])
    return ref, "\n".join(texts), first_verse_url


def resolve_ref_text(lookup: BibleTextLookup, ref_str: str) -> tuple[str, str, str]:
    """Given a ref string like '빌립보서 3:13-14', return (formatted_ref, joined_text, first_verse_url).
    The URL is the per-verse timestamped URL of the first verse in the range (may be empty).
    Whole-chapter ref → first 3 verses."""
    try:
        ref = BibleRef.parse(ref_str)
    except ValueError:
        return ref_str, "", ""
    if ref.verse_start is None:
        return pick_first_n_verses(lookup, ref.book, ref.chapter, n=3)
    texts = []
    for v in range(ref.verse_start, (ref.verse_end or ref.verse_start) + 1):
        t = lookup.get(ref.book, ref.chapter, v)
        if t:
            texts.append(t)
    first_verse_url = lookup.get_url(ref.book, ref.chapter, ref.verse_start)
    return ref.format(), "\n".join(texts), first_verse_url


class ScheduleBuilder:
    def __init__(self, bible: BibleTextLookup, youtube: YoutubeUrlLookup,
                 template: str):
        self.bible = bible
        self.youtube = youtube
        self.template = template
        self.summary = {
            "total": 0,
            "meaningful": 0,
            "regular": 0,
            "needs_thread": 0,
            "missing_youtube": [],
            "missing_text": [],
        }

    def build_from_year_plan(self, plan_rows: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for entry in plan_rows:
            d = date.fromisoformat(entry["date"])
            day_kind = entry.get("day_kind", "regular") or "regular"
            label = entry.get("label", "") or ""
            ref_str = entry.get("bible_ref", "") or ""
            if ref_str:
                ref_formatted, text, verse_url = resolve_ref_text(self.bible, ref_str)
            else:
                ref_formatted, text, verse_url = "", "", ""
            row = self._make_row(d, day_kind, label, ref_formatted, text, verse_url)
            rows.append(row)
            if day_kind == "meaningful":
                self.summary["meaningful"] += 1
            else:
                self.summary["regular"] += 1
            self.summary["total"] += 1
        return rows

    def _make_row(self, d: date, day_kind: str, label: str,
                  bible_ref: str, bible_text: str, verse_url: str = "") -> dict:
        # Per-verse timestamped URL preferred; fall back to book/chapter-level
        url = verse_url
        if not url:
            try:
                ref = BibleRef.parse(bible_ref)
                url = self.youtube.get(ref.book, ref.chapter)
                if not url:
                    self.summary["missing_youtube"].append(f"{ref.book} {ref.chapter}")
            except ValueError:
                pass
        if not bible_text:
            self.summary["missing_text"].append(bible_ref)

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


def load_bible_csv(path: Path) -> BibleTextLookup:
    data: dict[tuple[str, int, int], str] = {}
    urls: dict[tuple[str, int, int], str] = {}
    with path.open("r", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            book = row["book"].strip()
            chapter = int(row["chapter"])
            verse = int(row["verse"])
            text = row["text"]
            data[(book, chapter, verse)] = text
            url = (row.get("video_url") or "").strip()
            if url:
                urls[(book, chapter, verse)] = url
    return BibleTextLookup(data, urls)


def load_youtube_csv(path: Path) -> YoutubeUrlLookup:
    data: dict[tuple[str, int], str] = {}
    with path.open("r", encoding="utf-8-sig") as f:
        reader = _csv.DictReader(f)
        for row in reader:
            book = row["book"].strip()
            chapter = int(row["chapter"])
            url = row["video_url"]
            data[(book, chapter)] = url
    return YoutubeUrlLookup(data)


def load_year_plan(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig") as f:
        return list(_csv.DictReader(f))


def print_summary(summary: dict):
    print()
    print(f"Built {summary['total']} schedule entries:")
    print(f"  📅 {summary['meaningful']} meaningful days, {summary['regular']} regular days")
    print(f"  🧵 {summary['needs_thread']} entries need thread (over 280 weight)")
    if summary["missing_youtube"]:
        unique = sorted(set(summary["missing_youtube"]))
        print(f"  ⚠️  {len(unique)} chapters missing YouTube URL:")
        for s in unique[:10]:
            print(f"        - {s}")
        if len(unique) > 10:
            print(f"        ...({len(unique) - 10} more)")
    if summary["missing_text"]:
        unique = sorted(set(summary["missing_text"]))
        print(f"  ⚠️  {len(unique)} refs missing bible text:")
        for s in unique[:10]:
            print(f"        - {s}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--year-plan", type=Path, default=None,
                        help="Override year_plan CSV path (default: data/year_plan_<YEAR>.csv)")
    parser.add_argument("--bible-csv", type=Path, default=Path("data/bible_text.csv"))
    parser.add_argument("--youtube-csv", type=Path, default=Path("data/youtube_videos.csv"))
    parser.add_argument("--dry-run", action="store_true",
                        help="Print preview rows without uploading to Sheet")
    parser.add_argument("--preview-count", type=int, default=5)
    args = parser.parse_args(argv)

    year_plan_path = args.year_plan or Path(f"data/year_plan_{args.year}.csv")
    for p in (args.bible_csv, args.youtube_csv, year_plan_path):
        if not p.exists():
            raise SystemExit(f"Required file not found: {p}")

    bible = load_bible_csv(args.bible_csv)
    yt = load_youtube_csv(args.youtube_csv)
    plan_rows = load_year_plan(year_plan_path)

    creds = _json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    from src.lib.sheets_client import SheetsClient
    sheets = SheetsClient(creds_dict=creds, sheet_id=sheet_id)
    config = sheets.get_config()
    template = config.get("tweet_template", "{bible_text}\n\n— {bible_ref}\n\n🎧 {youtube_url}")

    builder = ScheduleBuilder(bible, yt, template)
    rows = builder.build_from_year_plan(plan_rows)

    if args.dry_run:
        print(f"DRY RUN — would upload {len(rows)} rows. First {args.preview_count}:")
        for r in rows[:args.preview_count]:
            print(r)
    else:
        sheets.write_schedule_rows(rows)
        print(f"Uploaded {len(rows)} rows to Sheet.")

    print_summary(builder.summary)


if __name__ == "__main__":
    main()
