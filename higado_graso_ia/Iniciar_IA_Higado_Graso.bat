@echo off
cd /d "%~dp0"
title IA Higado Graso
echo ============================================================
echo   IA para deteccion y gradacion de higado graso
echo ============================================================
echo.
echo   El modelo ya viene entrenado: para diagnosticar no hace
echo   falta entrenar.
echo.
echo   Si vuelve a entrenar: el entrenamiento correcto completo
echo   son 150 epocas en total =
echo     5 modelos de validacion cruzada x 25 epocas  (125)
echo   + 1 modelo final x 25 epocas                    ( 25)
echo   En la pestana "Entrenar modelo" deje "Epocas por modelo"
echo   en 25 (valor por defecto). Con tarjeta NVIDIA tarda unos
echo   90 minutos; sin ella, varias horas.
echo.
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "programa\IA_Higado_Graso.py"
) else if exist "%USERPROFILE%\.venvs\higado_graso_ia\Scripts\pythonw.exe" (
    start "" "%USERPROFILE%\.venvs\higado_graso_ia\Scripts\pythonw.exe" "programa\IA_Higado_Graso.py"
) else (
    echo   No se encontro Python con las librerias necesarias.
    echo   Ejecute primero Instalar.bat ^(requiere internet^).
    echo.
    pause
    exit /b 1
)
echo   Abriendo el programa...
ping -n 7 127.0.0.1 >nul
