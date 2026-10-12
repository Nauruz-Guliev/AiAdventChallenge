# Opens TCP port 8000 in Windows Firewall (needs Administrator).
$rule = "Day30 LLM service 8000"
if (-not (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName $rule -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 8000 -Profile Private | Out-Null
  Write-Host "Firewall rule added: $rule"
} else {
  Write-Host "Firewall rule already exists: $rule"
}
