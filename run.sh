#!/usr/bin/env bash
# Bible Twitter Bot - runner (Bash: git-bash / WSL / macOS / Linux)
# Usage:
#   ./run.sh seed
#   ./run.sh build [--dry]
#   ./run.sh post [YYYY-MM-DD] [--dry]

set -euo pipefail
cd "$(dirname "$0")"

# === Config ===
KEYS_FILE="keys"
CREDS_FILE="bible-bot-495101-79a9f9b89bab.json"
SHEET_ID="1SJIZBY4mvPO1tHSB5r0OwZvUarIdFxh9p62H1nWGXQE"

# Detect venv python (Windows vs Unix layout)
if   [ -x ".venv/Scripts/python.exe" ]; then VENV_PYTHON=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ];        then VENV_PYTHON=".venv/bin/python"
else
    echo "ERROR: venv not found at .venv/"
    echo "Create one: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# === Console + env setup ===
export PYTHONIOENCODING="utf-8"
export GOOGLE_SHEET_ID="$SHEET_ID"
export GOOGLE_SHEETS_CREDS="$(cat "$CREDS_FILE")"

if [ -f "$KEYS_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # match VAR_NAME=value (skip comments and blanks)
        if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.+)$ ]]; then
            export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
        fi
    done < "$KEYS_FILE"
fi

# === Subcommand router ===
cmd="${1:-}"
shift || true

usage() {
    cat <<EOF
Bible Twitter Bot - bash runner

Usage:
  ./run.sh seed                          # Seed Sheet config + meaningful_days
  ./run.sh build [--dry]                 # Build 2026 schedule
  ./run.sh post [YYYY-MM-DD] [--dry]     # Post tweet
  ./run.sh measure                       # Re-measure all mp4 durations
  ./run.sh detect-starts                 # Detect chapter audio starts in book mp4s
  ./run.sh verify [--no-youtube]         # Audit YouTube → book → chapter → verse chain
  ./run.sh timestamps                    # Rebuild data/bible_text.csv with timestamps
  ./run.sh upload-bible                  # Push bible_text.csv to Google Sheets
  ./run.sh refresh-urls [--dry]          # Refresh schedule.youtube_url from bible_text.csv
EOF
    exit 1
}

case "$cmd" in
    seed)
        "$VENV_PYTHON" -m scripts.seed_sheet
        ;;
    build)
        args=(--year 2026)
        for a in "$@"; do
            [ "$a" = "--dry" ] && args+=(--dry-run)
        done
        "$VENV_PYTHON" -m scripts.build_schedule "${args[@]}"
        ;;
    post)
        args=()
        date_arg=""
        for a in "$@"; do
            if [ "$a" = "--dry" ]; then
                args+=(--dry-run)
            elif [[ "$a" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
                date_arg="$a"
            fi
        done
        [ -n "$date_arg" ] && args+=(--date "$date_arg")
        "$VENV_PYTHON" -m src.post_today "${args[@]}"
        ;;
    measure)
        "$VENV_PYTHON" -m scripts.measure_mp4_durations
        ;;
    detect-starts)
        "$VENV_PYTHON" -m scripts.detect_book_chapter_starts
        ;;
    verify)
        "$VENV_PYTHON" -m scripts.verify_videos "$@"
        ;;
    timestamps)
        "$VENV_PYTHON" -m scripts.build_verse_timestamps
        ;;
    upload-bible)
        "$VENV_PYTHON" -m scripts.upload_bible_text
        ;;
    refresh-urls)
        args=()
        for a in "$@"; do
            [ "$a" = "--dry" ] && args+=(--dry-run)
        done
        "$VENV_PYTHON" -m scripts.refresh_schedule_urls "${args[@]}"
        ;;
    *)
        usage
        ;;
esac
