@echo off
setlocal
set "DESTINO=%~dp0Iniciar_IA_Higado_Graso.bat"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$w = New-Object -ComObject WScript.Shell; $l = $w.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\IA Higado Graso.lnk'); $l.TargetPath = $env:DESTINO; $l.WorkingDirectory = (Split-Path $env:DESTINO); $l.WindowStyle = 1; $l.IconLocation = $env:SystemRoot + '\System32\imageres.dll,190'; $l.Description = 'IA para deteccion y gradacion de higado graso'; $l.Save()"
if errorlevel 1 (
    echo No se pudo crear el acceso directo en el escritorio.
) else (
    echo Acceso directo "IA Higado Graso" creado en el escritorio.
)
if /i not "%~1"=="silencioso" pause
