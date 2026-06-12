@echo off
:: setup_task.bat — Ejecutar UNA sola vez para registrar la tarea programada.
:: Despues de esto, la app inicia sin UAC ni ventanas CMD.

net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo Registrando tarea programada AsusFanControl...

schtasks /delete /tn "AsusFanControl" /f >nul 2>&1

schtasks /create /tn "AsusFanControl" ^
  /tr "wscript.exe \"%~dp0launcher.vbs\"" ^
  /sc ONLOGON ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea registrada correctamente.
    echo      Ahora puedes usar start.vbs para lanzar la app sin UAC.
    echo      La app tambien iniciara automaticamente al encender el equipo.
) else (
    echo.
    echo [ERROR] No se pudo registrar la tarea.
)

pause
