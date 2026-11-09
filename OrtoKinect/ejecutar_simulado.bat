@echo off
cd /d "%~dp0"
python app.py --simulado
if errorlevel 1 pause
