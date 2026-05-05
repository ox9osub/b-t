@echo off
setlocal enabledelayedexpansion

REM Bible Twitter Bot - runner (Windows CMD)
REM Usage:
REM   run.cmd seed
REM   run.cmd build [--dry]
REM   run.cmd post [YYYY-MM-DD] [--dry]

cd /d "%~dp0"

REM === Config ===
set "VENV_PYTHON=.\.venv\Scripts\python.exe"
set "KEYS_FILE=keys"
set "CREDS_FILE=bible-bot-495101-79a9f9b89bab.json"
set "SHEET_ID=1SJIZBY4mvPO1tHSB5r0OwZvUarIdFxh9p62H1nWGXQE"

REM === Console + env setup ===
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "GOOGLE_SHEET_ID=%SHEET_ID%"

if not exist "%VENV_PYTHON%" (
    echo ERROR: venv not found at %VENV_PYTHON%
    echo Run: ^"C:\ProgramData\miniconda3\python.exe^" -m venv .venv ^&^& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

REM Load creds JSON into single env var (newlines stripped; JSON parser ignores them)
for /f "usebackq delims=" %%V in (`%VENV_PYTHON% -c "print(open('%CREDS_FILE%', encoding='utf-8').read().replace(chr(10), '').replace(chr(13), ''))"`) do set "GOOGLE_SHEETS_CREDS=%%V"

REM Load keys file lines (skip comments and blanks)
if exist "%KEYS_FILE%" (
    for /f "usebackq tokens=1* eol=# delims==" %%K in ("%KEYS_FILE%") do (
        if not "%%K"=="" if not "%%L"=="" set "%%K=%%L"
    )
)

REM === Subcommand router ===
set "CMD=%~1"

if /i "%CMD%"=="seed"  goto :seed
if /i "%CMD%"=="build" goto :build
if /i "%CMD%"=="post"  goto :post
goto :usage

:seed
"%VENV_PYTHON%" -m scripts.seed_sheet
exit /b %errorlevel%

:build
set "ARGS=--year 2026"
if /i "%~2"=="--dry" set "ARGS=%ARGS% --dry-run"
if /i "%~3"=="--dry" set "ARGS=%ARGS% --dry-run"
"%VENV_PYTHON%" -m scripts.build_schedule %ARGS%
exit /b %errorlevel%

:post
set "ARGS="
set "DATE_ARG="
shift
:post_parse
if "%~1"=="" goto :post_run
if /i "%~1"=="--dry" (set "ARGS=%ARGS% --dry-run") else (set "DATE_ARG=%~1")
shift
goto :post_parse
:post_run
if not "%DATE_ARG%"=="" set "ARGS=%ARGS% --date %DATE_ARG%"
"%VENV_PYTHON%" -m src.post_today %ARGS%
exit /b %errorlevel%

:usage
echo Bible Twitter Bot - CMD runner
echo.
echo Usage:
echo   run.cmd seed                          ^# Seed Sheet config + meaningful_days
echo   run.cmd build [--dry]                 ^# Build 2026 schedule
echo   run.cmd post [YYYY-MM-DD] [--dry]     ^# Post tweet
echo.
echo Examples:
echo   run.cmd seed
echo   run.cmd build --dry
echo   run.cmd post --dry 2026-12-25
echo   run.cmd post                          ^# post today
exit /b 1
