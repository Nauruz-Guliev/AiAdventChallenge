# Поднять локальный сервер для chat/index.html и открыть чат в браузере.
# Важно: открывать index.html двойным кликом нельзя — с file:// Ollama отдаёт 403 (CORS).
$port = 8000
$dir  = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Сервирую $dir на http://localhost:$port"
Write-Host "Закрыть — Ctrl+C"
Start-Process "http://localhost:$port"

Set-Location $dir
python -m http.server $port
