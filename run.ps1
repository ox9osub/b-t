# Bible Twitter Bot - runner (PowerShell)
# Usage:
#   .\run.ps1 seed
#   .\run.ps1 build [--dry]
#   .\run.ps1 post [YYYY-MM-DD] [--dry]

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# === Config ===
$VENV_PYTHON = ".\.venv\Scripts\python.exe"
$KEYS_FILE   = "keys"
$CREDS_FILE  = "bible-bot-495101-79a9f9b89bab.json"
$SHEET_ID    = "1SJIZBY4mvPO1tHSB5r0OwZvUarIdFxh9p62H1nWGXQE"

# === Console + env setup ===
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING    = "utf-8"
$env:GOOGLE_SHEET_ID     = $SHEET_ID
$env:GOOGLE_SHEETS_CREDS = Get-Content $CREDS_FILE -Raw

if (Test-Path $KEYS_FILE) {
    foreach ($line in (Get-Content $KEYS_FILE -Encoding UTF8)) {
        if ($line -match '^([A-Z_][A-Z0-9_]*)=(.+)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
}

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "ERROR: venv not found at $VENV_PYTHON" -ForegroundColor Red
    Write-Host "Run: & 'C:\ProgramData\miniconda3\python.exe' -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

# === Subcommand router ===
$cmd = if ($args.Count -gt 0) { $args[0] } else { "" }
$rest = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }

function Invoke-Build {
    $extra = @("--year", "2026")
    if ($rest -contains "--dry") { $extra += "--dry-run" }
    & $VENV_PYTHON -m scripts.build_schedule @extra
}

function Invoke-Post {
    $extra = @()
    $date  = $null
    foreach ($a in $rest) {
        if ($a -eq "--dry")                    { $extra += "--dry-run" }
        elseif ($a -match '^\d{4}-\d{2}-\d{2}$') { $date = $a }
    }
    if ($date) { $extra += @("--date", $date) }
    & $VENV_PYTHON -m src.post_today @extra
}

switch ($cmd) {
    "seed"  { & $VENV_PYTHON -m scripts.seed_sheet }
    "build" { Invoke-Build }
    "post"  { Invoke-Post }
    default {
        Write-Host "Bible Twitter Bot - PowerShell runner"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  .\run.ps1 seed                          # Seed Sheet config + meaningful_days"
        Write-Host "  .\run.ps1 build [--dry]                 # Build 2026 schedule"
        Write-Host "  .\run.ps1 post [YYYY-MM-DD] [--dry]     # Post tweet"
        Write-Host ""
        Write-Host "Examples:"
        Write-Host "  .\run.ps1 seed"
        Write-Host "  .\run.ps1 build --dry"
        Write-Host "  .\run.ps1 post --dry 2026-12-25"
        Write-Host "  .\run.ps1 post                          # post today"
        exit 1
    }
}
