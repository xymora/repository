@echo off
chcp 65001 >nul
title Moto autonoma evolutiva
cd /d "%~dp0"
if errorlevel 1 (
    echo No se pudo entrar a la carpeta del simulador: "%~dp0"
    pause
    exit /b 1
)
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
%PY% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Instalando Pillow para la imagen satelital de las calles reales...
    %PY% -m pip install pillow
)

%PY% -c "import numba" >nul 2>nul
if errorlevel 1 (
    echo Instalando numba para usar todos los nucleos de la CPU...
    %PY% -m pip install numba
)
where nvidia-smi >nul 2>nul
if %errorlevel%==0 (
    %PY% -c "from numba import cuda; assert cuda.is_available()" >nul 2>nul
    if errorlevel 1 (
        echo Tarjeta NVIDIA detectada: instalando numba-cuda para usar la GPU...
        %PY% -m pip install "numba-cuda[cu12]"
    )
)
%PY% -c "import aceleracion as A; print('Hardware detectado: ' + A.resumen())"

echo Abriendo el simulador... (esta consola muestra el avance de cada generacion)
echo.
%PY% "%~dp0main.py" %*
if errorlevel 1 pause
