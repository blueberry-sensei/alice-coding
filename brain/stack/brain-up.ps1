# ALICE CODING — dựng brain stack bằng MỘT LỆNH (Windows / Docker Desktop).
#
# Mặc định: KÉO IMAGE dựng sẵn về chạy. Không cần git, không cần source, không build gì.
# Tự động: tính BRAIN_ID riêng cho project, cấp cổng trống, sinh SAG_SECRET_KEY (lưu NGOÀI
# repo), pull image + chạy nền + pull model embedding.
#
# MỖI PROJECT MỘT BRAIN: tên compose project suy từ đường dẫn kho tri thức, nên chạy song song
# nhiều project không đụng container, không đụng cổng, không chung dữ liệu.
#
# CHẾ ĐỘ DEV (chỉ dành cho người phát triển chính alice-brain / alice-core): đặt CẢ HAI
# ALICE_APP_PATH và ALICE_CORE_PATH trong file .env của brain (đường dẫn in ra ở cuối lệnh)
# → launcher build từ source trên máy thay vì dùng image đã publish.
$ErrorActionPreference = "Stop"
$Stack = $PSScriptRoot
Set-Location $Stack

# Ghi toàn bộ output ra file: dựng stack lỗi ở bước nào thì còn cái mà đọc sau khi cửa sổ đã
# đóng. Transcript lỗi thì bỏ qua, không để nó chặn việc dựng.
$LogDir = Join-Path (Split-Path $Stack -Parent) ".logs"
try {
  if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force $LogDir | Out-Null }
  Start-Transcript -Path (Join-Path $LogDir "brain-up.log") -Append | Out-Null
  $script:TranscriptOn = $true
} catch {
  Write-Host "[log] Cannot write the transcript ($($_.Exception.Message)); console output only."
  $script:TranscriptOn = $false
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "!! Node 18+ required (brain-env.js resolves the brain identity)."; exit 1
}

# Danh tinh + cong + secret: tinh o MOT cho (brain-env.js) de launcher, cli.js va compose
# khong bao gio lech nhau. File .env cua brain nam NGOAI repo - xem BRAIN_ENV_FILE.
$envLines = & node (Join-Path $Stack "brain-env.js") --powershell
if ($LASTEXITCODE -ne 0) { Write-Host "!! brain-env.js failed."; exit 1 }
$envLines | ForEach-Object { Invoke-Expression $_ }

$ComposeFiles = @("-f", (Join-Path $Stack "compose.yaml"))

if ($env:BRAIN_MODE -eq "dev") {
  # Kiem tra that, khong tin loi khai trong .env: sai duong dan ma van chay tiep thi loi hien
  # ra o giua luc build voi thong bao kho hieu.
  foreach ($pair in @(@("ALICE_APP_PATH", "apps/api"), @("ALICE_CORE_PATH", "pyproject.toml"))) {
    $dir = [Environment]::GetEnvironmentVariable($pair[0])
    if (-not (Test-Path (Join-Path $dir $pair[1]))) {
      Write-Host "!! $($pair[0]) is wrong: $dir"
      Write-Host "   That directory must contain '$($pair[1])'. Fix it in: $($env:BRAIN_ENV_FILE)"
      exit 1
    }
  }
  $ComposeFiles += @("-f", (Join-Path $Stack "compose.dev.yaml"))
  Write-Host "DEV mode: building from local sources."
  Write-Host "  ALICE_APP_PATH  = $($env:ALICE_APP_PATH)"
  Write-Host "  ALICE_CORE_PATH = $($env:ALICE_CORE_PATH)"
  # additional_contexts (compose >= 2.17) can BuildKit.
  $env:COMPOSE_DOCKER_CLI_BUILD = "1"
  $env:DOCKER_BUILDKIT = "1"
}

if ($env:BIND_ADDRESS -ne "127.0.0.1") {
  Write-Host "!! WARNING: BIND_ADDRESS=$($env:BIND_ADDRESS) exposes the brain off this machine over PLAIN HTTP."
  Write-Host "   API keys typed in the UI would travel the network in the clear. Trusted networks only."
}

Write-Host "BRAIN_ID     = $($env:BRAIN_ID)"
Write-Host "Mode         = $($env:BRAIN_MODE)"
Write-Host "BIND_ADDRESS = $($env:BIND_ADDRESS)"
Write-Host "Ports        = web $($env:WEB_PORT) | api $($env:API_PORT)"

$dc = @("compose", "-p", $env:BRAIN_ID) + $ComposeFiles + @("--env-file", $env:BRAIN_ENV_FILE)

if ($env:BRAIN_MODE -eq "dev") {
  docker @dc up -d --build
} else {
  Write-Host "Pulling ALICE images (a few minutes the first time)..."
  docker @dc pull
  if ($LASTEXITCODE -ne 0) {
    Write-Host "!! Could not pull the images. Check your network, or they may not be published yet."
    Write-Host "   Have the sources locally? Set ALICE_APP_PATH + ALICE_CORE_PATH in $($env:BRAIN_ENV_FILE)"
    Write-Host "   to build from them instead of pulling."
    if ($script:TranscriptOn) { try { Stop-Transcript | Out-Null } catch {} }
    exit 1
  }
  docker @dc up -d
}
if ($LASTEXITCODE -ne 0) {
  Write-Host "!! Build/startup failed. Full log: $(Join-Path $LogDir 'brain-up.log')"
  if ($script:TranscriptOn) { try { Stop-Transcript | Out-Null } catch {} }
  exit 1
}

Write-Host "Pulling the bge-m3 embedding model (a few minutes the first time)..."
docker @dc exec -T embedding ollama pull bge-m3
if ($LASTEXITCODE -ne 0) { Write-Host "!! Model pull failed. Run it manually: npm run brain:pull" }

Write-Host ""
Write-Host "==> ALICE app: http://localhost:$($env:WEB_PORT)"
Write-Host "==> Stack build log: $(Join-Path $LogDir 'brain-up.log')"
Write-Host "==> API + engine log: $(Join-Path $env:BRAIN_LOGS 'sag-api.log')"
Write-Host "==> Brain config (OUTSIDE the repo, holds a secret - never commit): $($env:BRAIN_ENV_FILE)"
if ($script:TranscriptOn) { try { Stop-Transcript | Out-Null } catch {} }
