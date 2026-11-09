@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Instalacion - IA Higado Graso
echo ============================================================
echo   Instalacion de la IA para higado graso
echo   Se necesita conexion a internet (descarga de 300 MB a 3 GB)
echo ============================================================
echo.

set "RUTA=%~dp0"
if not "%RUTA:~115,1%"=="" (
    echo ERROR: la carpeta esta en una ruta demasiado larga:
    echo   "%~dp0"
    echo Windows no admite rutas de mas de 260 caracteres y algunas librerias no se instalarian.
    echo Mueva la carpeta a una ubicacion mas corta, por ejemplo C:\IA_Higado_Graso, y vuelva a ejecutar este archivo.
    goto :fin_error
)

set "PY="
call :buscar_python
if defined PY goto :hay_python

echo [1/4] No se encontro Python 3.10, 3.11 o 3.12. Instalando Python 3.11...
where winget >nul 2>&1
if not errorlevel 1 (
    winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements
    call :buscar_python
)
if defined PY goto :hay_python

set "INST=%TEMP%\python-3.11.9-amd64.exe"
echo       Descargando el instalador oficial desde python.org...
curl.exe -L --fail -o "%INST%" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if errorlevel 1 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -OutFile $env:INST"
)
if not exist "%INST%" goto :error_descarga
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = Get-AuthenticodeSignature $env:INST; if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike '*Python Software Foundation*') { exit 1 }"
if errorlevel 1 (
    echo ERROR: el instalador descargado no tiene una firma valida de Python Software Foundation.
    del "%INST%" >nul 2>&1
    goto :fin_error
)
echo       Instalando Python 3.11 para este usuario ^(no requiere administrador^)...
"%INST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_tcltk=1 Include_pip=1 Include_test=0
del "%INST%" >nul 2>&1
call :buscar_python
if not defined PY (
    echo ERROR: Python no quedo instalado. Instalelo a mano desde https://www.python.org/downloads/
    echo marcando "Add Python to PATH" y vuelva a ejecutar este archivo.
    goto :fin_error
)

:hay_python
echo [1/4] Python encontrado: "%PY%"

if exist "venv\Scripts\python.exe" (
    echo [2/4] El entorno virtual ya existe; se reutiliza.
) else (
    echo [2/4] Creando el entorno virtual en la carpeta venv...
    "%PY%" -m venv venv
    if errorlevel 1 goto :fin_error
)
set "VPY=venv\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip --quiet

set "GPU=0"
nvidia-smi >nul 2>&1
if not errorlevel 1 set "GPU=1"
if /i "%~1"=="cpu" set "GPU=0"
set "IDX=https://download.pytorch.org/whl/cpu"
if "%GPU%"=="1" set "IDX=https://download.pytorch.org/whl/cu121"
if "%GPU%"=="0" echo [3/4] Sin tarjeta NVIDIA ^(o se pidio la opcion cpu^): se instala PyTorch para procesador ^(unos 300 MB^).
if "%GPU%"=="1" echo [3/4] Tarjeta NVIDIA detectada: se instala PyTorch con CUDA ^(unos 2.5 GB^).
"%VPY%" -m pip install torch==2.5.1 torchvision==0.20.1 --index-url %IDX%
if errorlevel 1 goto :fin_error
echo       Instalando el resto de las librerias...
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :fin_error

echo [4/4] Comprobando la instalacion...
"%VPY%" -c "import torch, torchvision, numpy, scipy, sklearn, pandas, matplotlib, PIL, pydicom, tkinter; print('      Todo correcto. PyTorch', torch.__version__, '| GPU:', torch.cuda.is_available())"
if errorlevel 1 goto :fin_error

call "%~dp0Crear_acceso_directo.bat" silencioso
echo.
echo ============================================================
echo   Instalacion terminada.
echo   Abra el programa con el icono "IA Higado Graso" del escritorio
echo   o con doble clic en Iniciar_IA_Higado_Graso.bat
echo   Si despues mueve esta carpeta a otro lugar, el programa sigue
echo   funcionando; solo ejecute Crear_acceso_directo.bat para
echo   actualizar el icono del escritorio.
echo ============================================================
pause
exit /b 0

:buscar_python
for %%V in (3.10 3.11 3.12) do (
    if not defined PY (
        for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
    )
)
if not defined PY (
    for /f "delims=" %%P in ('python -c "import sys; v = sys.version_info[:2]; (3, 10) <= v <= (3, 12) and print(sys.executable)" 2^>nul') do set "PY=%%P"
)
for %%V in (310 311 312) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
)
exit /b 0

:error_descarga
echo ERROR: no se pudo descargar Python. Revise la conexion a internet.
:fin_error
echo.
echo La instalacion no se completo. Revise los mensajes de arriba.
pause
exit /b 1
