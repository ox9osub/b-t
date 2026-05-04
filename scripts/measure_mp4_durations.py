"""Walk temp/tts_result-slow/{book}/{chapter}/*.mp4 and write a CSV of durations."""

from __future__ import annotations

import csv
import struct
import sys
from pathlib import Path

ROOT = Path("temp/tts_result-slow")
OUTPUT_CSV = Path("temp/mp4_durations.csv")
TOP_FOLDER_NAME = "tts_result-slow"


def _read_atom_header(buf: bytes, offset: int) -> tuple[int, str, int] | None:
    """Return (atom_total_size, atom_type, payload_offset) or None at EOF."""
    if offset + 8 > len(buf):
        return None
    size = struct.unpack(">I", buf[offset : offset + 4])[0]
    atom_type = buf[offset + 4 : offset + 8].decode("ascii", errors="replace")
    payload_offset = offset + 8
    if size == 1:
        if offset + 16 > len(buf):
            return None
        size = struct.unpack(">Q", buf[offset + 8 : offset + 16])[0]
        payload_offset = offset + 16
    elif size == 0:
        size = len(buf) - offset
    return size, atom_type, payload_offset


def _find_atom(buf: bytes, start: int, end: int, target: str) -> tuple[int, int] | None:
    """Linear scan for atom `target` between [start, end). Return (payload_start, atom_end)."""
    pos = start
    while pos < end:
        header = _read_atom_header(buf, pos)
        if header is None:
            return None
        size, atom_type, payload_off = header
        atom_end = pos + size
        if atom_type == target:
            return payload_off, atom_end
        pos = atom_end
    return None


def mp4_duration_seconds(path: Path) -> float:
    """Parse moov/mvhd atom to extract duration in seconds."""
    data = path.read_bytes()
    moov = _find_atom(data, 0, len(data), "moov")
    if moov is None:
        raise ValueError("no moov atom")
    moov_payload, moov_end = moov
    mvhd = _find_atom(data, moov_payload, moov_end, "mvhd")
    if mvhd is None:
        raise ValueError("no mvhd atom")
    mvhd_payload, _ = mvhd
    if mvhd_payload + 4 > len(data):
        raise ValueError("truncated mvhd")
    version = data[mvhd_payload]
    p = mvhd_payload + 4  # skip version (1) + flags (3)
    if version == 1:
        # creation_time(8) + modification_time(8) + timescale(4) + duration(8)
        if p + 28 > len(data):
            raise ValueError("truncated mvhd v1")
        timescale = struct.unpack(">I", data[p + 16 : p + 20])[0]
        duration = struct.unpack(">Q", data[p + 20 : p + 28])[0]
    else:
        # creation_time(4) + modification_time(4) + timescale(4) + duration(4)
        if p + 16 > len(data):
            raise ValueError("truncated mvhd v0")
        timescale = struct.unpack(">I", data[p + 8 : p + 12])[0]
        duration = struct.unpack(">I", data[p + 12 : p + 16])[0]
    if timescale == 0:
        raise ValueError("timescale is zero")
    return duration / timescale


def _filename_sort_key(name: str) -> tuple[int, int | str, str]:
    stem = Path(name).stem
    if stem.lstrip("-").isdigit():
        return (0, int(stem), name)
    return (1, name, name)


def _chapter_sort_key(name: str) -> tuple[int, int | str]:
    if name.lstrip("-").isdigit():
        return (0, int(name))
    return (1, name)


def collect_rows() -> list[tuple[str, str, str, str, str]]:
    if not ROOT.is_dir():
        print(f"error: {ROOT} not found", file=sys.stderr)
        sys.exit(1)
    rows: list[tuple[str, str, str, str, str]] = []
    succeeded = 0
    failed = 0
    books = sorted([p for p in ROOT.iterdir() if p.is_dir()], key=lambda p: p.name)
    for book in books:
        chapters = sorted(
            [p for p in book.iterdir() if p.is_dir()],
            key=lambda p: _chapter_sort_key(p.name),
        )
        for chapter in chapters:
            files = sorted(
                [p for p in chapter.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"],
                key=lambda p: _filename_sort_key(p.name),
            )
            for f in files:
                try:
                    seconds = mp4_duration_seconds(f)
                    duration_str = f"{seconds:.3f}"
                    succeeded += 1
                except (OSError, ValueError, struct.error) as exc:
                    print(f"warn: {f}: {exc}", file=sys.stderr)
                    duration_str = ""
                    failed += 1
                rows.append((TOP_FOLDER_NAME, book.name, chapter.name, f.name, duration_str))
    print(
        f"total={len(rows)} succeeded={succeeded} failed={failed} output={OUTPUT_CSV}",
        file=sys.stderr,
    )
    return rows


def write_csv(rows: list[tuple[str, str, str, str, str]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["folder", "subfolder1", "subfolder2", "filename", "duration_sec"])
        writer.writerows(rows)


def main() -> None:
    rows = collect_rows()
    write_csv(rows)


if __name__ == "__main__":
    main()
