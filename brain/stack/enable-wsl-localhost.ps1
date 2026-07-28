# ALICE CODING — bật WSL "mirrored networking" để http://localhost mở được từ Windows
# khi Docker chạy bằng Docker CE bên trong WSL (Docker Desktop thì không cần).
# Chạy MỘT LẦN (PowerShell):  powershell -File knowledge\brain\stack\enable-wsl-localhost.ps1
# ⚠️ Ghi %USERPROFILE%\.wslconfig và tắt toàn bộ WSL (wsl --shutdown) để áp dụng.
$ErrorActionPreference = "Stop"
$cfg = Join-Path $env:USERPROFILE ".wslconfig"

Write-Host "Yeu cau: Windows 11 + WSL >= 2.0 (kiem: 'wsl --version'; neu cu: 'wsl --update')." -ForegroundColor Cyan

if (Test-Path $cfg) {
  $c = Get-Content $cfg -Raw
  if ($c -match "networkingMode") {
    Write-Host ".wslconfig da co 'networkingMode'. Mo kiem tra cho chac: $cfg" -ForegroundColor Yellow
    Write-Host "Can dong:  networkingMode=mirrored   (trong muc [wsl2]). Sau do chay: wsl --shutdown"
    exit 0
  }
  Write-Host ".wslconfig da ton tai — them thu cong 2 dong sau roi luu:" -ForegroundColor Yellow
  Write-Host "  [wsl2]"
  Write-Host "  networkingMode=mirrored"
  Write-Host "File: $cfg   (sau do chay: wsl --shutdown, roi chay lai stack)"
  exit 0
}

Set-Content $cfg "[wsl2]`r`nnetworkingMode=mirrored`r`n" -Encoding utf8
Write-Host "Da tao $cfg voi mirrored networking." -ForegroundColor Green
Write-Host "Tat WSL de ap dung (cac phien WSL dang chay se dong)..." -ForegroundColor Yellow
wsl --shutdown
Write-Host ""
Write-Host "XONG. Buoc tiep:" -ForegroundColor Green
Write-Host "  1) bash knowledge/brain/stack/brain-up.sh"
Write-Host "  2) Open the project URL printed by `npm run brain`"
