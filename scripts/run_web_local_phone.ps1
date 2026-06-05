# Start the Horalix web app on the LAN so a phone on the same Wi-Fi can pair via QR.
#
#   pwsh scripts/run_web_local_phone.ps1                 # auto-detect LAN IP
#   pwsh scripts/run_web_local_phone.ps1 -Ip 192.168.1.21 -ApiPort 8010
#
# A phone cannot reach http://localhost on the laptop, so the QR + API URLs must
# use the laptop's LAN IP. For phones that require HTTPS camera access, deploy the
# frontend to Netlify and point NEXT_PUBLIC_API_URL at a public HTTPS backend.
param([string]$Ip = "", [int]$ApiPort = 8010, [int]$WebPort = 3000)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

if (-not $Ip) {
  $Ip = (
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -match "^(192\.168\.|10\.|172\.)" } |
    Select-Object -First 1 -ExpandProperty IPAddress
  )
}
if (-not $Ip) {
  Write-Host "Could not auto-detect a LAN IP. Pass -Ip <your-lan-ip>." -ForegroundColor Yellow
  Write-Host "Run: python scripts/print_local_network_urls.py"
  exit 1
}

Set-Location (Join-Path $repo "apps/web")
$env:NEXT_PUBLIC_API_URL = "http://${Ip}:${ApiPort}"
$env:NEXT_PUBLIC_APP_URL = "http://${Ip}:${WebPort}"

Write-Host "Web app on http://${Ip}:${WebPort}  (API ${env:NEXT_PUBLIC_API_URL})" -ForegroundColor Green
Write-Host "Backend CORS must allow http://${Ip}:${WebPort} (HORALIX_CORS_ORIGINS)."
Write-Host "Phone: open http://${Ip}:${WebPort}/analysis/setup -> choose 'Capture with phone'."
npm run dev -- --hostname 0.0.0.0 --port $WebPort
