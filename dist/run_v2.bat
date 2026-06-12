@echo off
:: ASUS Fan Control v2 - Launcher
:: Ejecuta el script Python directamente con pythonw.exe para evitar bloqueos de antivirus
:: PsExec eleva a SYSTEM (requerido por AsusWinIO64.dll)

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: -i = interactivo, -s = SYSTEM, -d = no esperar
:: pythonw.exe no abre ventana de consola y es ejecutable de confianza para AV
"%~dp0PsExec.exe" -i -s -d "C:\Users\javi2\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe" "%~dp0asus_fan_control.py"
