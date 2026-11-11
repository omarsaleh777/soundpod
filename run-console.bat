@echo off
cd /d "%~dp0"
python -m soundpod
if errorlevel 1 pause
