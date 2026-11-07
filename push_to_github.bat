@echo off
title Push AutoReach AI to GitHub (soban9633-tech)
color 0b

echo ========================================================
echo        AutoReach AI - GitHub Repo Push Script
echo ========================================================
echo.
echo Repo URL: https://github.com/soban9633-tech/AutoReach-AI.git
echo Account: soban9633-tech (soban9633@gmail.com)
echo.

set PATH=%LOCALAPPDATA%\Programs\MinGit\cmd;%LOCALAPPDATA%\Programs\MinGit\mingw64\bin;%PATH%

echo Staging files...
git add .
git commit -m "feat: AutoReach AI complete project push" 2>nul

echo.
echo ========================================================
echo [INSTRUCTION]: 
echo Agar samne "Sign in with your browser" ka pop-up aye, 
echo to us par click karein. Browser khud verify kar le ga!
echo ========================================================
echo.

git push -u origin main

echo.
if %ERRORLEVEL% equ 0 (
    echo ========================================================
    echo  SUCCESS! Mubarak ho, project GitHub par push ho gaya!
    echo  Apni repo refresh kar ke dekhein:
    echo  https://github.com/soban9633-tech/AutoReach-AI
    echo ========================================================
) else (
    echo ========================================================
    echo  Push me koi masla aya. 
    echo  Agar token mangay to apna GitHub Personal Token paste karein.
    echo ========================================================
)

echo.
pause
