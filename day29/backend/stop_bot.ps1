$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*app.main*' }
if (-not $procs) { Write-Host "Bot is not running."; exit 0 }
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force; Write-Host ("Stopped PID " + $p.ProcessId) }
Write-Host "Done."
