@echo off
chcp 65001 >nul
title F-15 Eagle evolutivo - entrenamiento rapido
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

echo Entrenamiento rapido sin graficos de las 13 misiones (Ctrl+C detiene y guarda)
echo.
%PY% "%~dp0entrenar_rapido.py" %*
pause
