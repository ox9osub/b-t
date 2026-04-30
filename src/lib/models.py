from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


_REF_PATTERN = re.compile(
    r"^\s*(?P<book>[^\d\s]+)\s+(?P<chapter>\d+)(?::(?P<vstart>\d+)(?:-(?P<vend>\d+))?)?\s*$"
)


@dataclass(frozen=True)
class BibleRef:
    book: str
    chapter: int
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None

    @classmethod
    def parse(cls, text: str) -> "BibleRef":
        m = _REF_PATTERN.match(text)
        if not m:
            raise ValueError(f"Invalid Bible reference: {text!r}")
        book = m.group("book")
        chapter = int(m.group("chapter"))
        vstart = int(m.group("vstart")) if m.group("vstart") else None
        vend = int(m.group("vend")) if m.group("vend") else vstart
        return cls(book=book, chapter=chapter, verse_start=vstart, verse_end=vend)

    def format(self) -> str:
        if self.verse_start is None:
            return f"{self.book} {self.chapter}"
        if self.verse_end == self.verse_start:
            return f"{self.book} {self.chapter}:{self.verse_start}"
        return f"{self.book} {self.chapter}:{self.verse_start}-{self.verse_end}"


@dataclass
class ScheduleEntry:
    date: date
    day_kind: str        # "meaningful" or "regular"
    label: str
    bible_ref: str
    bible_text: str
    youtube_url: str
    char_count: int = 0
    needs_thread: bool = False
    posted_at: Optional[datetime] = None
    tweet_id: Optional[str] = None
    error: str = ""

    def already_posted(self) -> bool:
        return self.tweet_id is not None and self.tweet_id != ""
