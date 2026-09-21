# Registers two Windows Task Scheduler tasks (run once, as the logged-in user):
#   Sekretaerin Relay   – relay/supervisor.py at logon, restarts forever, hidden window
#   Sekretaerin Doctor  – relay/doctor.py every 10 minutes
# Remove: schtasks /Delete /TN "Sekretaerin Relay" /F ; schtasks /Delete /TN "Sekretaerin Doctor" /F

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = Join-Path $root ".venv\Scripts\pythonw.exe"   # pythonw = no console window
$pyc = Join-Path $root ".venv\Scripts\python.exe"

$relayAction = New-ScheduledTaskAction -Execute $py -Argument "-m relay.supervisor" -WorkingDirectory $root
$relayTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$relaySettings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "Sekretaerin Relay" -Action $relayAction -Trigger $relayTrigger -Settings $relaySettings -Force | Out-Null

$docAction = New-ScheduledTaskAction -Execute $py -Argument "-m relay.doctor" -WorkingDirectory $root
$docTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 10)
$docSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Sekretaerin Doctor" -Action $docAction -Trigger $docTrigger -Settings $docSettings -Force | Out-Null

Get-ScheduledTask -TaskName "Sekretaerin *" | Select-Object TaskName, State
