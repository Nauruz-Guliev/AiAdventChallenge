# Печатает LAN-адрес, по которому сервис доступен другим устройствам.
Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object {
    $_.IPAddress -notlike '127.*' -and
    $_.PrefixOrigin -ne 'WellKnown'
  } |
  Select-Object IPAddress, InterfaceAlias |
  Format-Table -AutoSize
Write-Host "Сервис слушает http://<IP выше>:8000"
