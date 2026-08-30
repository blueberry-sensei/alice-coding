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

# Model nào phải tải về: đọc từ .env thật của brain, không ghim cứng. Ghim cứng "bge-m3" thì
# người đổi SAG_EMBEDDING_MODEL sẽ có một API trỏ tới model chưa bao giờ được pull.
$EmbeddingModel = "bge-m3"
if (Test-Path $env:BRAIN_ENV_FILE) {
  foreach ($line in Get-Content $env:BRAIN_ENV_FILE) {
    if ($line -match '^\s*SAG_EMBEDDING_MODEL\s*=\s*(.+?)\s*$') { $EmbeddingModel = $Matches[1] }
  }
}

$ComposeFiles = @("-f", (Join-Path $Stack "compose.yaml"))

# Embedding dung chung toan may: mot container Ollama phuc vu moi project thay vi N ban sao cua
# cung mot model. Phai dung TRUOC brain, vi compose.embedding-shared.yaml gan api vao network
# `alice-embedding` bang `external: true` - network chua ton tai thi `up` hong ngay.
$EmbeddingMode = if ($env:ALICE_EMBEDDING_MODE) { $env:ALICE_EMBEDDING_MODE } else { "shared" }
$HubArgs = @("compose", "-p", "alice-embedding", "-f", (Join-Path $Stack "embedding-hub.yaml"))

if ($EmbeddingMode -eq "external") {
  # Nguoi dung da co embedding API cua rieng ho. Khong dung Ollama, khong pull model:
  # 1,2 GB tai ve cho mot container khong ai goi toi la ngon tai nguyen doi lay so khong.
  $ExternalUrl = if ($env:SAG_EMBEDDING_BASE_URL) { $env:SAG_EMBEDDING_BASE_URL } else { "set in the brain .env" }
  Write-Host "Embedding    = external ($ExternalUrl) - nothing is started or downloaded"
} elseif ($EmbeddingMode -eq "shared") {
  $ComposeFiles += @("-f", (Join-Path $Stack "compose.embedding-shared.yaml"))
  Write-Host "Embedding    = shared (one Ollama container for this whole machine)"
  docker @HubArgs up -d
  if ($LASTEXITCODE -ne 0) {
    Write-Host "!! Could not start the shared embedding container."
    Write-Host "   Fall back to one per project: put ALICE_EMBEDDING_MODE=project in $($env:BRAIN_ENV_FILE)"
    if ($script:TranscriptOn) { try { Stop-Transcript | Out-Null } catch {} }
    exit 1
  }
} else {
  Write-Host "Embedding    = project (a private Ollama container for this brain)"
}

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

if ([string]::IsNullOrWhiteSpace($env:BIND_ADDRESS)) {
  $env:BIND_ADDRESS = "127.0.0.1"
}

if ($env:BIND_ADDRESS -ne "127.0.0.1") {
  Write-Host "!! WARNING: BIND_ADDRESS=$($env:BIND_ADDRESS) exposes the brain off this machine over PLAIN HTTP."
  Write-Host "   API keys typed in the UI would travel the network in the clear. Trusted networks only."
}

Write-Host "BRAIN_ID     = $($env:BRAIN_ID)"
Write-Host "BRAIN_HOST   = $($env:BRAIN_HOST)"
Write-Host "Mode         = $($env:BRAIN_MODE)"
Write-Host "BIND_ADDRESS = $($env:BIND_ADDRESS)"
Write-Host "Ports        = web $($env:WEB_PORT) | api $($env:API_PORT)"

$dc = @("compose", "-p", $env:BRAIN_ID) + $ComposeFiles + @("--env-file", $env:BRAIN_ENV_FILE)

if ($env:BRAIN_MODE -eq "dev") {
  docker @dc up -d --build
} else {
  Write-Host "Pulling ALICE images (a few minutes the first time)..."
  # `docker compose pull` KHONG nhin `deploy.replicas`: no keo image cua MOI service khai trong
  # file, ke ca `embedding` dang o replicas=0. O che do external/shared do la vai tram MB tai ve
  # cho mot container khong bao gio khoi dong. Chi keo image cua nhung service SE chay that.
  $PullServices = @("api", "web")
  if ($env:ALICE_EMBEDDING_REPLICAS -ne "0") { $PullServices += "embedding" }
  docker @dc pull @PullServices
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

if ($EmbeddingMode -eq "external") {
  Write-Host "Skipping the model download: this brain uses your own embedding endpoint."
} else {
  Write-Host "Pulling the $EmbeddingModel embedding model (a few minutes the first time)..."
  if ($EmbeddingMode -eq "shared") {
    # Model chi tai MOT lan cho ca may; project thu hai tro di buoc nay xong ngay.
    docker @HubArgs exec -T embedding ollama pull $EmbeddingModel
  } else {
    docker @dc exec -T embedding ollama pull $EmbeddingModel
  }
  if ($LASTEXITCODE -ne 0) { Write-Host "!! Model pull failed. Run it manually: npm run brain:pull" }
}

Write-Host ""
Write-Host "==> ALICE app: http://$($env:BRAIN_HOST):$($env:WEB_PORT)"
Write-Host "==> Stack build log: $(Join-Path $LogDir 'brain-up.log')"
Write-Host "==> API + engine log: $(Join-Path $env:BRAIN_LOGS 'sag-api.log')"
Write-Host "==> Brain config (OUTSIDE the repo, holds a secret - never commit): $($env:BRAIN_ENV_FILE)"
if ($script:TranscriptOn) { try { Stop-Transcript | Out-Null } catch {} }
