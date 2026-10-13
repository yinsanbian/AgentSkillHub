@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%~dp0skill-hub\scripts\gui.py"
) else (
    python "%~dp0skill-hub\scripts\gui.py"
)
if ERRORLEVEL 1 (
  echo.
  echo Could not launch Agent Skill Hub. Verify Python 3.10+ and Tkinter are installed.
  pause
)
