@echo off
cd /d D:\Desktop\docutranslate-main
.\.venv\Scripts\python.exe -m docutranslate.cli -i --with-mcp --host 127.0.0.1 --port 8010 --cors
pause