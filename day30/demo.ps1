param(
  [string]$ApiKeys = "demo-key",
  [int]$Port = 8000,
  [switch]$NoBrowser
)
# Демо «одной кнопкой»: проверяет Ollama, поднимает шлюз, открывает чат с уже введённым ключом.
# Использование:  .\demo.ps1            (ключ demo-key)
#                 .\demo.ps1 -ApiKeys "мой-ключ" -NoBrowser
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$backend = Join-Path $PSScriptRoot "backend"
Set-Location $backend

Write-Host "[1/4] Проверяю Ollama..." -ForegroundColor Cyan
try {
  $null = Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 5
} catch {
  Write-Host "Ollama не отвечает на localhost:11434. Запусти Ollama и повтори." -ForegroundColor Red
  exit 1
}

Write-Host "[2/4] Перезапускаю шлюз..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*app.main*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$env:API_KEYS = $ApiKeys
$env:REQUIRE_API_KEY = "true"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath (Join-Path $backend ".venv\Scripts\python.exe") `
  -ArgumentList "-m", "app.main" -WorkingDirectory $backend -WindowStyle Minimized

Write-Host "[3/4] Жду готовности сервиса..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
  Start-Sleep -Milliseconds 500
  try { $null = Invoke-RestMethod "http://localhost:$Port/health"; $ok = $true; break } catch {}
}
if (-not $ok) {
  Write-Host "Сервис не поднялся. Смотри окно с 'python -m app.main'." -ForegroundColor Red
  exit 1
}

$url = "http://localhost:$Port/?key=$ApiKeys"
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host "[4/4] Готово." -ForegroundColor Green
Write-Host "  Чат на этом ПК:  $url"
if ($ip) { Write-Host "  С телефона (в той же Wi-Fi): http://${ip}:8000/?key=$ApiKeys" }
Write-Host "  Стоп: закрой минимизированное окно Python." -ForegroundColor DarkGray

if (-not $NoBrowser) { Start-Process $url }
