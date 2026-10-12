# Открывает порт 8000 в брандмауэре Windows (нужны права администратора).
$rule = "Day30 LLM service 8000"
if (-not (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName $rule -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 8000 -Profile Private | Out-Null
  Write-Host "Правило добавлено: $rule"
} else {
  Write-Host "Правило уже есть: $rule"
}
