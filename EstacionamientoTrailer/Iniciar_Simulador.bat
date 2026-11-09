@echo off
chcp 65001 >nul
title Estacionamiento evolutivo
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if errorlevel 1 (
        echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY=py -3"
)

echo Abriendo el simulador... (esta consola muestra el avance de cada generacion)
echo.
%PY% main.py %*
if errorlevel 1 pause
