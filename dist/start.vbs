' start.vbs — dispara la tarea programada AsusFanControl (sin UAC, sin ventanas)
Set oShell = CreateObject("WScript.Shell")
oShell.Run "schtasks /run /tn ""AsusFanControl""", 0, False
