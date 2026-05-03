# Bible Text → YouTube Timestamps

## Goal

Add per-verse YouTube link and start time to `data/bible_text.csv`, so each row identifies exactly when its verse begins inside the corresponding YouTube audio video.

## Inputs

- `data/bible_text.csv` — `book,chapter,verse,text` (1 row per verse)
- `data/youtube_videos.csv` — `book,chapter,video_id,video_url,title`
  - `chapter > 0`: per-chapter video (Genesis only in current dataset)
  - `chapter = 0`: single video covering the whole book (all other books)
- `temp/mp4_durations.csv` — `folder,subfolder1,subfolder2,filename,duration_sec`
  - Built by `scripts/measure_mp4_durations.py`. Required to be up to date.

## Output

`data/bible_text.csv` rewritten with two new trailing columns:

```
book,chapter,verse,text,video_url,start_seconds,start_hms
창세기,1,1,태초에 하나님이 천지를 창조하시니라,https://youtu.be/abc123?t=3,3.000,00:00:03
창세기,1,2,...,https://youtu.be/abc123?t=8,8.557,00:00:08
```

Columns added:
- `video_url`: YouTube URL with `?t={int_seconds}` jump-to-time parameter (e.g., `https://youtu.be/abc?t=83`)
- `start_seconds`: float seconds, 3 decimal places (`f"{s:.3f}"`)
- `start_hms`: `HH:MM:SS` form, integer seconds (floor of `start_seconds`); zero-padded; supports `>= 24:00:00` if a video exceeds 24 hours (it won't in practice but format does not pad-truncate)

Encoding: `utf-8-sig`. Sort order preserved from input (no row reordering).

## Mapping book → YouTube video

`data/bible_text.csv` uses full book names (`창세기`, `요한계시록` …); `data/youtube_videos.csv` uses the same convention. Lookup rule:

- If book is **창세기** (Genesis): match by `(book == '창세기', chapter == c)` — per-chapter video.
- Otherwise: match by `(book == B, chapter == 0)` — single book video.

If a verse's row has no matching YouTube video row, leave `video_url`, `start_seconds`, `start_hms` empty and increment a `missing_video` counter for the end-of-run summary.

## Concat structure (verified empirically)

The composition of every YouTube-uploaded video has been verified against `temp/mp4_durations.csv`:

**Chapter video** (`temp/tts_result-slow/{book}/0/{책이름}-{N}장.mp4`):
```
[3.0s background2 chapter title pad] + verse_1.mp4 + verse_2.mp4 + … + verse_M.mp4
```
Verified: `chapter_video_dur ≈ 3.0 + Σ verse durations` for 1188 / 1189 chapters within ~0.01 s.

**Book video** (`temp/tts_result-slow/{short}/{책이름}.mp4`):
```
[3.0s pad] + chapter_1_video + [3.0s pad] + chapter_2_video + … + [3.0s pad] + chapter_n_video
```
Verified: `book_video_dur ≈ Σ chapter_video_dur + n × 3.0` for all 66 books within ~0.07 s (cumulative concat float error).

The 3-second pad before chapter 1 is treated as a **book intro** (the "A model"). The first sample row produced will be sanity-checked by the user clicking the resulting `?t=` link; if the actual verse plays 3 s later than the timestamp suggests, the formula will be revised to the "B model" (no leading book intro; trailing 3 s outro instead).

## Timestamp formula

For a verse `v` in chapter `c` (1-indexed) of book `B`:

**Genesis (per-chapter video):**
```
start_seconds(c, v) = 3.0 + Σ_{u=1..v-1} verse_dur(B, c, u)
```

**Other books (single book video, A model):**
```
chapter_offset(c) = c × 3.0 + Σ_{j=1..c-1} chapter_video_dur(B, j)
start_seconds(B, c, v) = chapter_offset(c) + 3.0 + Σ_{u=1..v-1} verse_dur(B, c, u)
```

Where:
- `verse_dur(B, c, u)` = duration of `temp/tts_result-slow/{book_short}/{c}/{u}.mp4`
- `chapter_video_dur(B, j)` = duration of `temp/tts_result-slow/{book_short}/0/{책이름}-{j}장.mp4`
- `book_short` is the directory name in `temp/tts_result-slow/` (e.g. `창`, `유`); the script needs a full-name → short-name map, derivable from `youtube_videos.csv` titles (`{책이름}.mp4` filenames in the durations CSV).

**Lead-time offset.** A `TIMESTAMP_LEAD_SEC = 2.0` constant is subtracted from each computed start when building the output URL/columns (clamped at 0). This is a UX choice: clicking a verse URL lands 2 seconds before the verse begins, so the first syllable isn't cut off by buffering or seek delay. The pure formulas above describe the *actual* verse start within the video; the value written to `start_seconds` / `start_hms` and the `?t=` URL are `max(0, formula - TIMESTAMP_LEAD_SEC)`.

## Known anomalies

**민수기 20장 24~29절** — the source verse mp4 `temp/tts_result-slow/민/20/24.mp4` is corrupt (48 bytes, no `moov` atom). The chapter video `민수기-20장.mp4` (303.310 s) was built without the standard 3 s title pad and without verses 24-29; the YouTube book video reflects that. For these 6 rows: emit `video_url` (entire-book URL with `?t=` pointing at the chapter offset, i.e. start of where chapter 20 begins) but leave `start_seconds` and `start_hms` empty so a click does not silently land on wrong audio. The script logs these as `MISSING_AUDIO` warnings.

The script must also detect any other rows with empty `duration_sec` in `mp4_durations.csv` along the cumulative sum path and treat those verses (and all subsequent verses in the same chapter) as `MISSING_DURATION` — emit `video_url` only, log a warning, do not invent timestamps.

## Behavior

1. Load `youtube_videos.csv`; build `(book, chapter) → (video_id, video_url)` map. Build the `full_name → short_dir` map by walking `temp/tts_result-slow/`: for each book directory `{short}/`, find any `*.mp4` file directly inside (not in a `0/` or `N/` subfolder) — its stem is the full Korean book name (e.g. `유다서`, `갈라디아서`). The `mp4_durations.csv` script does not record these top-level files, so this mapping comes from the filesystem walk.
2. Load `mp4_durations.csv`; build `verse_dur[(short, c, v)]` and `chapter_video_dur[(short, c)]` dicts. Skip rows with empty `duration_sec`.
3. Load `bible_text.csv` rows in order, preserving input order.
4. For each row, look up the matching YouTube video and compute `start_seconds` per the formula. If any prerequisite duration is missing, mark the row `MISSING_DURATION` (or `MISSING_AUDIO` for known 민수기 20:24-29 case) and skip timestamp.
5. Emit new CSV with 7 columns (4 original + 3 new). Write atomically (write to `*.tmp` then rename).
6. Print summary: rows total, rows with timestamps, rows with `MISSING_VIDEO`, `MISSING_DURATION`, `MISSING_AUDIO`. List up to 20 problem rows.

## Verification

Built into the script (run automatically at end):

- For each book, recompute the book video duration as `Σ chapter_video_dur + n × 3.0`. Read the actual book video duration on disk via `mp4_duration_seconds` and assert `|computed - actual| < 1.0`. Any book exceeding this prints a warning.
- For each chapter (Genesis only), recompute `3.0 + Σ verse_dur` and compare to the stored chapter video duration; warn on any chapter exceeding 1.0 s difference (expect only 민수기 20).
- The user's manual sanity check: click `video_url` of `창세기 1:1` (Genesis chapter video — should land at exactly the start of "태초에…") and click `video_url` of `갈라디아서 1:1` (book video, A-model decisive test — should land at exactly the start of "바울은 사도된 것이…"). If either is off, revise model.

## Non-Goals

- Re-measuring mp4 durations (uses existing `temp/mp4_durations.csv`).
- Repairing the corrupt `민/20/24.mp4` or rebuilding any video.
- Rebuilding `data/youtube_videos.csv`.
- Crawling YouTube for actual server-side durations (local mp4s are the source of truth).
- Any UI / sheet upload step (downstream of this CSV).

## Run

```
.\.venv\Scripts\python.exe scripts/build_verse_timestamps.py
```

No CLI arguments; input/output paths are constants at the top of the script for easy editing. Re-runnable: idempotent on the same inputs (overwrites existing `video_url`/`start_seconds`/`start_hms` columns if present).

## Tests

`tests/test_build_verse_timestamps.py` (using small synthetic fixtures, not the real corpus):
- `test_genesis_chapter_video_formula`: synthetic Genesis ch1 with 3 verses, asserts `start = 3.0 + Σ prior`.
- `test_other_book_book_video_formula`: synthetic 2-chapter book, asserts chapter 2 verse 1 starts at `2*3 + ch1_dur + 3.0`.
- `test_url_includes_jump_param`: `video_url` ends with `?t={int(start_seconds)}`.
- `test_hms_formatting`: 0 → `00:00:00`, 83.7 → `00:01:23`, 3661.0 → `01:01:01`.
- `test_missing_video_row`: book missing from `youtube_videos.csv` → empty timestamp columns, counted as `MISSING_VIDEO`.
- `test_missing_duration_row`: empty `duration_sec` for a verse → that verse + subsequent verses in chapter empty, counted as `MISSING_DURATION`.
- `test_known_민수기_20_24_through_29`: constructs the known-bad case, asserts those 6 rows have `start_seconds` empty.
