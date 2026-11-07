@echo off
title AutoReach AI Tool
color 0b

echo ========================================================
echo         AutoReach AI - Excel Automation Tool
echo ========================================================
echo.
echo Starting application server...
echo.

set PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%

start "" "http://localhost:5000"
python app.py

pause
