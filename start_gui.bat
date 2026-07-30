@echo off
echo Starting Music Digger Web GUI...
set PYTHONPATH=.
.\.venv\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
pause
