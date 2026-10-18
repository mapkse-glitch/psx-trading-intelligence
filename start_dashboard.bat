@echo off
REM ===========================================================================
REM PSX Trading Intelligence Dashboard — Windows 11 Local Launcher
REM Runs 100% locally without cloud dependencies or LLM keys.
REM Default Local Data Root: %LOCALAPPDATA%\PSXTradingDashboard\ (override via PSX_DATA_DIR)
REM ===========================================================================
setlocal

cd /d "%~dp0"

if not defined PSX_PORT set PSX_PORT=8000
if not defined PSX_HOST set PSX_HOST=127.0.0.1

echo ===========================================================================
echo   PSX Trading Intelligence Dashboard (Local-First Terminal)
echo   Starting local FastAPI server on http://%PSX_HOST%:%PSX_PORT%
echo ===========================================================================

if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

start "" "http://%PSX_HOST%:%PSX_PORT%"
"%PYTHON_EXE%" -m uvicorn psx_app.main:app --host %PSX_HOST% --port %PSX_PORT%
pause
