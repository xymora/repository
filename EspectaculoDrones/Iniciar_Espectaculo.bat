@echo off
chcp 65001 >nul
title Espectaculo de drones
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

for %%M in (numpy scipy PIL pygame moderngl matplotlib imageio_ffmpeg) do (
    %PY% -c "import %%M" >nul 2>nul
    if errorlevel 1 (
        echo Instalando %%M...
        if "%%M"=="PIL" (%PY% -m pip install pillow) else if "%%M"=="imageio_ffmpeg" (%PY% -m pip install imageio-ffmpeg) else (%PY% -m pip install %%M)
    )
)

%PY% "%~dp0main.py" %*
if errorlevel 1 pause
