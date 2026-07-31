@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo   Running Tests (Pytest)
echo ========================================

set PYTHONPATH=.

.\.venv\Scripts\python.exe -m pytest tests/ -v

echo.
if %errorlevel% neq 0 (
    echo [ERROR] Some tests failed.
    exit /b %errorlevel%
)

echo [SUCCESS] All tests passed!
exit /b 0
