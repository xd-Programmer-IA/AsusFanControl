; ASUS Fan Control v2 - Inno Setup Script
; Requiere Inno Setup 6: https://jrsoftware.org/isinfo.php
; Compilar con: iscc setup.iss  (desde la carpeta que contiene dist\)

#define AppName     "ASUS Fan Control"
#define AppVersion  "2.0.0"
#define AppPublisher "ASUS Fan Control"
#define AppExeName  "AsusFanControlV2.exe"
#define LauncherBat "run_v2.bat"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=AsusFanControl_v2_Setup
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} v{#AppVersion}
; Icono del instalador (opcional — usar si tienes un .ico)
; SetupIconFile=assets\asus.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Iconos adicionales:"
Name: "startupicon"; Description: "Iniciar con Windows (requiere ejecutar el instalador como admin)"; GroupDescription: "Inicio automático:"

[Files]
; Ejecutable principal y DLL de hardware
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\AsusWinIO64.dll";  DestDir: "{app}"; Flags: ignoreversion
Source: "dist\PsExec.exe";        DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#LauncherBat}";   DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Acceso directo en Inicio (apunta al launcher que eleva a SYSTEM)
Name: "{group}\{#AppName}";         Filename: "{app}\{#LauncherBat}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
; Escritorio (opcional)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#LauncherBat}"; Tasks: desktopicon

[Registry]
; Registro en Agregar/Quitar Programas (lo hace Inno Setup automáticamente)
; Inicio con Windows via HKLM Run (solo si el usuario lo pide en la casilla)
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "AsusFanControl"; \
    ValueData: """{app}\{#LauncherBat}"""; \
    Tasks: startupicon; Flags: uninsdeletevalue

[Run]
; Ofrecer lanzar la app al terminar la instalación
Filename: "{app}\{#LauncherBat}"; \
    Description: "Iniciar {#AppName} ahora"; \
    Flags: postinstall nowait skipifsilent

[UninstallRun]
; Al desinstalar: devolver control del ventilador al BIOS
; (la app se cierra antes de que el desinstalador termine)
Filename: "taskkill"; Parameters: "/F /IM {#AppExeName}"; \
    Flags: runhidden waituntilterminated; RunOnceId: "KillApp"

[Code]
// Verificar que el sistema es 64-bit
function InitializeSetup(): Boolean;
begin
  if not Is64BitInstallMode then
  begin
    MsgBox('Esta aplicación requiere Windows de 64 bits.', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;
