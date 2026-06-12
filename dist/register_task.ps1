# register_task.ps1 — detecta Python y registra la tarea programada AsusFanControl
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Detectar pythonw.exe
$pyPath = $null
$patterns = @(
    "$env:LOCALAPPDATA\Python\*\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python*\pythonw.exe",
    "C:\Python*\pythonw.exe",
    "C:\Program Files\Python*\pythonw.exe"
)
foreach ($p in $patterns) {
    $f = Get-Item $p -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if ($f) { $pyPath = $f.FullName; break }
}
if (-not $pyPath) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { $pyPath = $cmd.Source }
}
# Guardar ruta para que launcher.vbs la use
if ($pyPath) {
    $pyPath | Out-File "$dir\python_path.txt" -Encoding ASCII -NoNewline
}

# 2. Obtener el usuario de la sesion activa (no el de UAC)
$user = (Get-WmiObject Win32_ComputerSystem).UserName
if ($user -match '\\') { $user = $user.Split('\')[1] }

# 3. Registrar tarea programada
$action    = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$dir\launcher.vbs`""
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -RunLevel Highest -LogonType Interactive
$settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit 0 -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "AsusFanControl" `
    -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Tarea AsusFanControl registrada para usuario: $user"
