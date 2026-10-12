param([string]$Key = "change-me-local-key", [string]$SvcHost = "localhost")
$ErrorActionPreference = "Stop"
$base = "http://${SvcHost}:8000"
Write-Host "health:" (Invoke-RestMethod "$base/health" | ConvertTo-Json -Compress)
$headers = @{ "X-API-Key" = $Key }
$body = @{ messages = @(@{ role = "user"; content = "Hello! Answer with one word." }); max_tokens = 16 } | ConvertTo-Json -Depth 5
Write-Host "chat:" (Invoke-RestMethod -Uri "$base/v1/chat/completions" -Method Post -Headers $headers -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 8)
