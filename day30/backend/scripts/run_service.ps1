param([string]$ApiKeys = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $ApiKeys) { $ApiKeys = $env:API_KEYS }
if (-not $ApiKeys) {
  $ApiKeys = "change-me-local-key"
  Write-Host "API_KEYS не задан — используется демо-ключ '$ApiKeys'." -ForegroundColor Yellow
}
$env:API_KEYS = $ApiKeys
$env:REQUIRE_API_KEY = "true"
Write-Host "День 30: локальный LLM-сервис" -ForegroundColor Cyan
& "$root\.venv\Scripts\python.exe" -m app.main
