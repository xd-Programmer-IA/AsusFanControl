' launcher.vbs — lanza asus_fan_control.py via PsExec como SYSTEM, sin ventanas
Dim d, cmd, oShell, pyPath, fso, configFile

d = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' Leer ruta de Python desde archivo de config (escrito por register_task.ps1)
Set fso = CreateObject("Scripting.FileSystemObject")
configFile = d & "python_path.txt"
If fso.FileExists(configFile) Then
    Dim f
    Set f = fso.OpenTextFile(configFile, 1)
    pyPath = Trim(f.ReadLine())
    f.Close
Else
    ' Fallback: ruta por defecto de este equipo
    pyPath = "C:\Users\javi2\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"
End If

cmd = Chr(34) & d & "PsExec.exe" & Chr(34) _
    & " -accepteula -i -s -d" _
    & " " & Chr(34) & pyPath & Chr(34) _
    & " " & Chr(34) & d & "asus_fan_control.py" & Chr(34)

Set oShell = CreateObject("WScript.Shell")
oShell.Run cmd, 0, False
