param([string]$ApiKeys = "")
$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $ApiKeys) { $ApiKeys = $env:API_KEYS }
if (-not $ApiKeys) {
  $ApiKeys = "change-me-local-key"
  Write-Host "API_KEYS is not set - using demo key '$ApiKeys'." -ForegroundColor Yellow
}
$env:API_KEYS = $ApiKeys
$env:REQUIRE_API_KEY = "true"
Write-Host "Day 30: private LLM service" -ForegroundColor Cyan
& "$root\.venv\Scripts\python.exe" -m app.main
