param(
  [string]$ApiKeys = "demo-key",
  [int]$Port = 8000,
  [switch]$NoBrowser
)
# One-command demo: checks Ollama, (re)starts the gateway, opens the chat with the key pre-filled.
# Usage:  .\demo.ps1
#         .\demo.ps1 -ApiKeys "my-key" -NoBrowser
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "backend"
Set-Location $backend

Write-Host "[1/4] Checking Ollama..." -ForegroundColor Cyan
try {
  $null = Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 5
} catch {
  Write-Host "Ollama is not responding on localhost:11434. Start Ollama and retry." -ForegroundColor Red
  exit 1
}

Write-Host "[2/4] Restarting gateway..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*app.main*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$env:API_KEYS = $ApiKeys
$env:REQUIRE_API_KEY = "true"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath (Join-Path $backend ".venv\Scripts\python.exe") `
  -ArgumentList "-m", "app.main" -WorkingDirectory $backend -WindowStyle Minimized

Write-Host "[3/4] Waiting for health..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  try { $null = Invoke-RestMethod "http://localhost:$Port/health"; $ok = $true; break } catch {}
}
if (-not $ok) {
  Write-Host "Service did not start. Check the minimized python window." -ForegroundColor Red
  exit 1
}

$url = "http://localhost:$Port/?key=$ApiKeys"
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host "[4/4] Ready." -ForegroundColor Green
Write-Host "  Chat (this PC): $url"
if ($ip) { Write-Host "  From phone (same Wi-Fi): http://${ip}:8000/?key=$ApiKeys" }
Write-Host "  Stop: close the minimized Python window." -ForegroundColor DarkGray

if (-not $NoBrowser) { Start-Process $url }
