@echo off
set PYTHONPATH=.
echo =========================================
echo Music Digger Pipeline
echo =========================================
echo.
if not "%~1"=="" (
    echo [1/6] Running Collection...
    .\.venv\Scripts\python.exe scripts\run_collection.py %*
) else (
    echo If you have a SoundCloud URL to analyze, paste it below.
    echo (Press Enter without typing anything to run a test track)
    echo.
    set /p TARGET_URL="URL: "
    
    echo.
    echo [1/6] Running Collection...
    if "%TARGET_URL%"=="" (
        .\.venv\Scripts\python.exe scripts\run_collection.py
    ) else (
        .\.venv\Scripts\python.exe scripts\run_collection.py "%TARGET_URL%"
    )
)
if %errorlevel% neq 0 (
    echo [ERROR] Collection failed.
    exit /b %errorlevel%
)

echo.
echo [2/6] Running Stem Separation (This may take a while)...
.\.venv\Scripts\python.exe scripts\run_separation.py
if %errorlevel% neq 0 (
    echo [ERROR] Stem Separation failed.
    exit /b %errorlevel%
)

echo.
echo [3/6] Running Feature Extraction...
.\.venv\Scripts\python.exe scripts\run_features.py
if %errorlevel% neq 0 (
    echo [ERROR] Feature Extraction failed.
    exit /b %errorlevel%
)

echo.
echo [4/6] Running Inference...
.\.venv\Scripts\python.exe scripts\run_inference.py
if %errorlevel% neq 0 (
    echo [ERROR] Inference failed.
    exit /b %errorlevel%
)

echo.
echo [5/6] Running Identify (Apple Music Match)...
.\.venv\Scripts\python.exe scripts\run_identify.py
if %errorlevel% neq 0 (
    echo [ERROR] Identify failed.
    exit /b %errorlevel%
)

echo.
echo [6/6] Running Sync (Apple Music Playlist)...
.\.venv\Scripts\python.exe scripts\run_sync.py
if %errorlevel% neq 0 (
    echo [ERROR] Sync failed.
    exit /b %errorlevel%
)

echo.
echo Pipeline finished successfully! You can now open the Web GUI to analyze tracks.
pause
