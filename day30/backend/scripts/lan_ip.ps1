# Prints the LAN address where the service is reachable from other devices.
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike '127.*' -and
    $_.PrefixOrigin -ne 'WellKnown'
  } |
  Select-Object IPAddress, InterfaceAlias |
  Format-Table -AutoSize
Write-Host "Service: http://<IP above>:8000"
