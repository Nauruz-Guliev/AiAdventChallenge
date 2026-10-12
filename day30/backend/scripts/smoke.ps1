param([string]$Key = "change-me-local-key", [string]$Host = "localhost")
$ErrorActionPreference = "Stop"
$base = "http://${Host}:8000"
Write-Host "health:" (Invoke-RestMethod "$base/health" | ConvertTo-Json -Compress)
$headers = @{ "X-API-Key" = $Key }
$body = @{ messages = @(@{ role = "user"; content = "Скажи одним словом: привет" }); max_tokens = 32 } | ConvertTo-Json -Depth 5
Write-Host "chat:" (Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -Headers $headers -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 8)
