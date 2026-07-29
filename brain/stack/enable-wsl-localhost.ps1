# ALICE CODING — cấu hình WSL một lần cho Docker CE chạy bên trong Ubuntu.
# Chạy từ thư mục knowledge bằng PowerShell:
#   npm run wsl:setup
#
# Script chỉ cập nhật + backup %USERPROFILE%\.wslconfig. Nó KHÔNG tự shutdown WSL vì thao tác đó
# dừng mọi distro/container đang chạy; người dùng chủ động chạy sau khi đã lưu công việc.
$ErrorActionPreference = "Stop"
$cfg = Join-Path $env:USERPROFILE ".wslconfig"
$backup = "$cfg.bak"

function Set-IniValue {
  param(
    [string]$Text,
    [string]$Section,
    [string]$Key,
    [string]$Value
  )

  $normalized = $Text -replace "`r`n", "`n"
  $lines = New-Object "System.Collections.Generic.List[string]"
  foreach ($line in ($normalized -split "`n")) {
    [void]$lines.Add($line)
  }

  $start = -1
  $end = $lines.Count
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Trim() -match '^\[([^\]]+)\]$') {
      if ($start -ge 0) {
        $end = $i
        break
      }
      if ($matches[1].Trim() -ieq $Section) {
        $start = $i
      }
    }
  }

  if ($start -ge 0) {
    while ($end -gt ($start + 1) -and -not $lines[$end - 1].Trim()) {
      $end--
    }
    for ($i = $start + 1; $i -lt $end; $i++) {
      $line = $lines[$i].Trim()
      if (-not $line -or $line.StartsWith("#") -or $line.StartsWith(";")) {
        continue
      }
      $eq = $line.IndexOf("=")
      if ($eq -gt 0 -and $line.Substring(0, $eq).Trim() -ieq $Key) {
        $lines[$i] = "$Key=$Value"
        return (($lines -join "`r`n").TrimEnd() + "`r`n")
      }
    }
    $lines.Insert($end, "$Key=$Value")
  } else {
    if ($lines.Count -gt 0 -and $lines[$lines.Count - 1].Trim()) {
      [void]$lines.Add("")
    }
    [void]$lines.Add("[$Section]")
    [void]$lines.Add("$Key=$Value")
  }

  return (($lines -join "`r`n").TrimEnd() + "`r`n")
}

Write-Host "Dang kiem tra/cap nhat WSL..." -ForegroundColor Cyan
wsl --update
if ($LASTEXITCODE -ne 0) {
  Write-Host "Khong cap nhat duoc WSL. Van tiep tuc cau hinh; neu localhost loi, chay lai: wsl --update" -ForegroundColor Yellow
}

$text = ""
if (Test-Path $cfg) {
  Copy-Item -LiteralPath $cfg -Destination $backup -Force
  $text = Get-Content -LiteralPath $cfg -Raw
  Write-Host "Da backup: $backup"
}

$text = Set-IniValue $text "general" "instanceIdleTimeout" "-1"
$text = Set-IniValue $text "wsl2" "vmIdleTimeout" "-1"
$text = Set-IniValue $text "wsl2" "networkingMode" "mirrored"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($cfg, $text, $utf8NoBom)

Write-Host "Da cap nhat: $cfg" -ForegroundColor Green
Write-Host ""
Write-Host "Anh huong: mirrored + giu distro/VM WSL chay; ap dung cho TAT CA project." -ForegroundColor Yellow
Write-Host "Khi da san sang dung moi distro/container WSL, chay:" -ForegroundColor Yellow
Write-Host "  wsl --shutdown"
Write-Host "  npm run brain"
Write-Host ""
Write-Host "Moi project tu sinh domain *.localhost + port rieng; khong sua hosts/DNS."
