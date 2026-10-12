# Запуск Telegram-бота (День 27) с корректной UTF-8 кодировкой консоли.
# Токен берётся из .env — этот скрипт его не читает и не показывает.
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $dir

chcp 65001 > $null
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Starting local Telegram bot... (model from .env)" -ForegroundColor Cyan
& ".venv\Scripts\python.exe" -m app.main
