import csv
from pathlib import Path
from scripts.build_schedule import load_bible_csv, load_youtube_csv


def test_load_bible_csv(tmp_path: Path):
    p = tmp_path / "bible.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "verse", "text"])
        w.writerow(["창세기", "1", "1", "태초에 하나님이"])
        w.writerow(["창세기", "1", "2", "땅이 혼돈하고"])

    lookup = load_bible_csv(p)
    assert lookup.get("창세기", 1, 1) == "태초에 하나님이"
    assert lookup.get("창세기", 1, 2) == "땅이 혼돈하고"


def test_load_youtube_csv(tmp_path: Path):
    p = tmp_path / "yt.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "chapter", "video_id", "video_url", "title"])
        w.writerow(["창세기", "1", "abc", "https://youtu.be/abc", "창세기 1장"])

    lookup = load_youtube_csv(p)
    assert lookup.get("창세기", 1) == "https://youtu.be/abc"
