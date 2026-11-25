@echo off
cd /d "%~dp0"
title Khata Book
echo Open http://127.0.0.1:8000/ in your browser after the server starts.
echo Keep this window open. Press Ctrl+C to stop the server.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" manage.py runserver
) else (
    python manage.py runserver
)
pause
