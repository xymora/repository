@echo off
chcp 65001 >nul
title Road Fighter evolutivo 0 (sin maestro)
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

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

%PY% -c "import numpy" >nul 2>nul
if errorlevel 1 (
    echo Instalando numpy...
    %PY% -m pip install numpy
)

%PY% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Instalando pygame para los graficos...
    %PY% -m pip install pygame
)

echo Abriendo el simulador... (esta consola muestra el avance de cada generacion)
echo.
%PY% "%~dp0main.py" %*
if errorlevel 1 pause
