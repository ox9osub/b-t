"""YouTube channel crawler — outputs data/youtube_videos.csv.

Usage:
    python -m scripts.crawl_youtube --channel <CHANNEL_URL>
"""
from __future__ import annotations
import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Optional

# Title parser: matches "<책이름> <숫자>장" (allowing trailing extras)
# Korean book name: any non-digit non-space sequence
_TITLE_RE = re.compile(r"^\s*([^\d\s]+(?:[^\d\s]+)*)\s+(\d+)장")


def parse_title(title: str) -> Optional[tuple[str, int]]:
    """Returns (book, chapter) or None."""
    m = _TITLE_RE.match(title)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def crawl_channel(channel_url: str) -> list[dict]:
    """Use yt-dlp to enumerate channel videos. Returns list of {book, chapter, video_id, video_url, title}."""
    import yt_dlp

    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
    }
    rows: list[dict] = []
    skipped: list[str] = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries", [])
        # Some channels have nested entries (tabs); flatten one level
        flat = []
        for e in entries:
            if e and e.get("_type") == "playlist":
                flat.extend(e.get("entries") or [])
            elif e:
                flat.append(e)

        for v in flat:
            title = v.get("title", "")
            vid = v.get("id", "")
            parsed = parse_title(title)
            if not parsed:
                skipped.append(title)
                continue
            book, chapter = parsed
            rows.append({
                "book": book,
                "chapter": chapter,
                "video_id": vid,
                "video_url": f"https://youtu.be/{vid}",
                "title": title,
            })

    print(f"Parsed: {len(rows)} videos, Skipped: {len(skipped)}")
    if skipped:
        print("Skipped titles (first 10):")
        for t in skipped[:10]:
            print(f"  - {t}")
    return rows


def write_csv(rows: list[dict], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["book", "chapter", "video_id", "video_url", "title"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} rows to {output_path}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, help="YouTube channel URL")
    parser.add_argument("--out", type=Path, default=Path("data/youtube_videos.csv"))
    args = parser.parse_args(argv)

    rows = crawl_channel(args.channel)
    if not rows:
        print("WARNING: 0 videos parsed. Check channel URL or title format.", file=sys.stderr)
        sys.exit(1)
    write_csv(rows, args.out)


if __name__ == "__main__":
    main()
