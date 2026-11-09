@echo off
chcp 65001 >nul
title Escuela de vuelo
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

echo Abriendo la escuela de vuelo... (esta consola muestra el avance de cada generacion)
echo Sigue entrenando el mejor cerebro guardado; para empezar de cero usa el boton
echo "Reiniciar desde cero" de la ventana.
echo.
%PY% main.py --entrenar --continuar %*
if errorlevel 1 pause
