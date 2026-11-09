@echo off
chcp 65001 >nul
title Emulador GBC con IA
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

for %%M in (numpy numba PIL sounddevice) do (
    %PY% -c "import %%M" >nul 2>nul
    if errorlevel 1 (
        echo Instalando %%M...
        if "%%M"=="PIL" (%PY% -m pip install pillow) else (%PY% -m pip install %%M)
    )
)

%PY% -c "import pypdf" >nul 2>nul
if errorlevel 1 (
    echo Instalando pypdf para leer instrucciones en PDF...
    %PY% -m pip install pypdf
)

%PY% -c "import imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo Instalando imageio-ffmpeg para grabar la pantalla...
    %PY% -m pip install imageio-ffmpeg
)

echo Abriendo el emulador... (la primera vez tarda unos segundos en compilar)
echo Esta consola muestra el avance de cada generacion.
echo.
%PY% "%~dp0main.py" %*
if errorlevel 1 pause
