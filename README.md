# ASUS Fan Control

Control avanzado de velocidad de ventiladores para laptops ASUS desde Windows.

![Logo](dist/Imagen1.png)

## Características

- Control manual de velocidad con slider (0–100%)
- Modos preestablecidos: Normal (35%), Equilibrado (50%), Rápido (100%), Auto
- Modo automático con umbrales de temperatura configurables
- Monitoreo en tiempo real de temperatura CPU y RPM del ventilador
- Inicio silencioso sin ventanas CMD ni solicitudes UAC (tras instalación)
- Ícono en bandeja del sistema
- Menú de Configuración y Acerca de integrados

## Requisitos

- Windows 10/11 (64-bit)
- Python 3.10+ con los paquetes: `customtkinter`, `Pillow`, `pystray`
- `AsusWinIO64.dll` (incluida — DLL de hardware ASUS)
- `PsExec.exe` (incluido — Sysinternals, para ejecutar como SYSTEM)

## Instalación

### Opción A — Instalador (recomendado)

1. Descarga `ASUS_FanControl_Setup_v2.0.0.exe` 

2. Ejecuta el instalador (pide UAC una sola vez)
3. El instalador:
   - Copia los archivos a `C:\Program Files\ASUS Fan Control\`
   - Detecta tu instalación de Python automáticamente
   - Registra la tarea programada para inicio silencioso
   - Crea acceso directo en Escritorio y Menú Inicio

### Opción B — Manual

```bat
1. Clona el repositorio o descarga el ZIP
2. Asegúrate de tener instalados: pip install customtkinter Pillow pystray
3. Ejecuta setup_task.bat UNA sola vez (UAC requerido)
4. Lanza la app con start.vbs (sin UAC, sin ventanas)
```

## Archivos principales

| Archivo | Descripción |
|---|---|
| `asus_fan_control.py` | Script principal de la aplicación |
| `dist/launcher.vbs` | Lanzador silencioso vía PsExec |
| `dist/start.vbs` | Lanzador para el usuario (dispara tarea programada) |
| `dist/register_task.ps1` | Registra la tarea en el Programador de tareas |
| `dist/setup_task.bat` | Alternativa manual para registrar la tarea |
| `setup.iss` | Script de Inno Setup para compilar el instalador |

## ¿Por qué requiere SYSTEM?

`AsusWinIO64.dll` accede directamente al Embedded Controller (EC) del hardware ASUS,
lo que requiere la cuenta SYSTEM de Windows. PsExec se usa únicamente para esta elevación.

## Créditos

- **Modificado por** [xd-Programmer-IA](https://github.com/xd-Programmer-IA/AsusFanControl)
- **Creado originalmente por** [Karmel0x](https://github.com/Karmel0x)

## Imagen referencia:


<img width="467" height="700" alt="Captura de pantalla 2026-06-11 234847" src="https://github.com/user-attachments/assets/d9bfb2c6-ec20-48c8-a9d4-5d8711c265a0" />

## Licencia

Este proyecto es de uso personal. `AsusWinIO64.dll` es propiedad de ASUS y
`PsExec.exe` es propiedad de Microsoft Sysinternals.
