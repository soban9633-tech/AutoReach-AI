@echo off
title Push AutoReach AI to GitHub
color 0b

echo ========================================================
echo        Pushing AutoReach AI to GitHub Repository
echo ========================================================
echo.

set PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%PATH%

echo Current remote:
git remote -v
echo.

echo Staging any recent changes...
git add .
git commit -m "update: AutoReach AI latest updates" 2>nul

echo.
echo Pushing to GitHub (main branch)...
echo If prompted, please authenticate with your GitHub account or Token.
echo.

git push -u origin main

echo.
if %ERRORLEVEL% equ 0 (
    echo ========================================================
    echo [SUCCESS] Project pushed to GitHub successfully!
    echo URL: https://github.com/soban9633-tech/AutoReach-AI
    echo ========================================================
) else (
    echo ========================================================
    echo [ERROR] Push failed. 
    echo Please make sure you have access to the repo, or use a
    echo GitHub Personal Access Token (PAT).
    echo ========================================================
)

echo.
pause
