@echo off
set PYTHONPATH=.
echo =========================================
echo Music Digger Pipeline
echo =========================================
echo.
echo 分析したいSoundCloudのURL（曲やプレイリスト）があれば
echo 下に貼り付けてEnterを押してください。
echo （何も入力せずにEnterを押すと、テスト用に自動で処理されます）
echo.
set /p TARGET_URL="URL: "

echo.
echo [1/3] Running Collection...
if "%TARGET_URL%"=="" (
    .\.venv\Scripts\python.exe scripts\run_collection.py
) else (
    .\.venv\Scripts\python.exe scripts\run_collection.py "%TARGET_URL%"
)

echo.
echo [2/3] Running Stem Separation (This may take a while)...
.\.venv\Scripts\python.exe scripts\run_separation.py

echo.
echo [3/3] Running Feature Extraction...
.\.venv\Scripts\python.exe scripts\run_features.py

echo.
echo Pipeline finished! You can now open the Web GUI to analyze tracks.
pause
