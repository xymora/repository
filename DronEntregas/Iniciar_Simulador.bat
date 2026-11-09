@echo off
chcp 65001 >nul
title Dron de entregas
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

%PY% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Instalando Pillow ^(para la imagen satelital^)...
    %PY% -m pip install --user pillow
)

%PY% -c "import imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo Instalando imageio-ffmpeg ^(para grabar la pantalla en video^)...
    %PY% -m pip install --user imageio-ffmpeg
)

echo Abriendo el simulador... (la primera vez que se usa una ciudad se descargan
echo su mapa y su imagen satelital; esta consola muestra el avance)
echo.
%PY% main.py %*
if errorlevel 1 pause
