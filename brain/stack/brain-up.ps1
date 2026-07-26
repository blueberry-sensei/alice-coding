# ALICE CODING — dựng brain stack bằng MỘT LỆNH (Windows / Docker Desktop).
# Tự động: tạo .env, sinh SAG_SECRET_KEY, LẤY hai repo nguồn, build + chạy + pull model.
# KHÔNG cần sửa .env tay (LLM key set trong app).
#
# Nguồn build (cả hai đều tự lấy, KHÔNG cần chuẩn bị gì):
#   alice-brain -> fork ứng dụng (apps/api + apps/web)
#   alice-core  -> engine ALICE CORE (src/alicecore)
# Đang phát triển chính hai repo đó? Đặt ALICE_APP_PATH / ALICE_CORE_PATH trong
# .env để build từ bản trên máy thay vì bản trên GitHub.
$ErrorActionPreference = "Stop"
$Stack = $PSScriptRoot
Set-Location $Stack

if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

$envmap = @{}
Get-Content ".env" | ForEach-Object {
  $l = $_.Trim()
  if ($l -and (-not $l.StartsWith("#")) -and $l.Contains("=")) {
    $p = $l.Split("=", 2); $envmap[$p[0].Trim()] = $p[1].Trim()
  }
}

function Env-Or($key, $fallback) {
  if ($envmap[$key]) { return $envmap[$key] } else { return $fallback }
}

$AppRepo  = Env-Or "ALICE_APP_REPO"  "https://github.com/blueberry-sensei/alice-brain.git"
$CoreRepo = Env-Or "ALICE_CORE_REPO" "https://github.com/blueberry-sensei/alice-core.git"
$AppRef   = Env-Or "ALICE_APP_REF"   "main"
$CoreRef  = Env-Or "ALICE_CORE_REF"  "main"

if (-not $envmap["SAG_SECRET_KEY"]) {
  $sk = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
  (Get-Content ".env") -replace '^SAG_SECRET_KEY=.*', "SAG_SECRET_KEY=$sk" | Set-Content ".env" -Encoding utf8
  $envmap["SAG_SECRET_KEY"] = $sk
  Write-Host "Da sinh SAG_SECRET_KEY."
}

function Resolve-Abs($p, $create) {
  if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $Stack $p }
  if ($create -and -not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
  return [System.IO.Path]::GetFullPath($p)
}

# Tro toi ban tren may neu .env khai bao; neu khong thi clone (ghim ref) vao .\<dir>.
function Resolve-Source($key, $repo, $ref, $dir, $mustContain, $what) {
  $raw = $envmap[$key]
  if ($raw) {
    $abs = Resolve-Abs $raw $false
    if (-not (Test-Path (Join-Path $abs $mustContain))) {
      Write-Host "!! $key sai: $abs"
      Write-Host "   Thu muc nay phai chua '$mustContain' ($what)."
      exit 1
    }
    return $abs
  }

  $abs = Join-Path $Stack $dir
  if (-not (Test-Path (Join-Path $abs $mustContain))) {
    Write-Host "Lay $dir ($ref)..."
    if (Test-Path $abs) { Remove-Item -Recurse -Force $abs }
    git clone --depth 1 --branch $ref $repo $abs
    if ($LASTEXITCODE -ne 0) { Write-Host "!! Khong clone duoc $repo (kiem mang / git)."; exit 1 }
  }
  elseif (Test-Path (Join-Path $abs ".git")) {
    # Thu muc do launcher tu clone -> LAM MOI. Khong co buoc nay thi moi lan chay
    # sau deu build tu source cu va ban cap nhat khong bao gio toi duoc nguoi dung.
    # `reset --hard` an toan vi day la ban sao chi-doc do launcher quan ly; ai muon
    # sua source thi dung ALICE_APP_PATH / ALICE_CORE_PATH (nhanh tren).
    Write-Host "Cap nhat $dir ($ref)..."
    # git ghi tien trinh ra stderr ngay khi thanh cong. PowerShell 5.1 goi moi dong
    # stderr cua native exe la NativeCommandError, nen voi $ErrorActionPreference =
    # "Stop" o dau file thi script DUNG HAN giua fetch va reset. Vi vay: KHONG
    # redirect stderr, chi ha ErrorActionPreference quanh hai lenh git roi xet
    # $LASTEXITCODE - do moi la tin hieu dung de biet git thanh cong hay khong.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
      git -C $abs fetch --depth 1 --quiet origin $ref
      if ($LASTEXITCODE -eq 0) {
        git -C $abs reset --hard --quiet FETCH_HEAD
        if ($LASTEXITCODE -ne 0) {
          Write-Host "!! Khong dat lai duoc $dir ve $ref - dung ban dang co."
        }
      } else {
        Write-Host "!! Khong fetch duoc $dir (kiem mang) - dung ban dang co."
      }
    } finally {
      $ErrorActionPreference = $prevEap
    }
  }
  if (-not (Test-Path (Join-Path $abs $mustContain))) {
    Write-Host "!! $dir tai ve nhung thieu '$mustContain' - repo nguon co the da doi cau truc."
    exit 1
  }
  return (Resolve-Path $abs).Path
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "!! Can git de lay source."; exit 1
}

$env:ALICE_APP_PATH  = Resolve-Source "ALICE_APP_PATH"  $AppRepo  $AppRef  "alice-brain" "apps/api"       "fork ung dung ALICE"
$env:ALICE_CORE_PATH = Resolve-Source "ALICE_CORE_PATH" $CoreRepo $CoreRef "alice-core"  "pyproject.toml" "engine ALICE CORE"

$bd = $envmap["BRAIN_DATA"]; if (-not $bd) { $bd = "../.sag-data" }
$env:BRAIN_DATA = Resolve-Abs $bd $true
$env:SAG_SECRET_KEY = $envmap["SAG_SECRET_KEY"]
if ($envmap["BIND_ADDRESS"]) { $env:BIND_ADDRESS = $envmap["BIND_ADDRESS"] } else { $env:BIND_ADDRESS = "127.0.0.1" }

# additional_contexts (compose >= 2.17) can BuildKit.
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
$env:DOCKER_BUILDKIT = "1"

Write-Host "ALICE_APP_PATH  = $($env:ALICE_APP_PATH)"
Write-Host "ALICE_CORE_PATH = $($env:ALICE_CORE_PATH)"
Write-Host "BRAIN_DATA      = $($env:BRAIN_DATA)"
Write-Host "BIND_ADDRESS    = $($env:BIND_ADDRESS)"
docker compose --env-file .env up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "!! Build/khoi dong that bai (xem log tren)."; exit 1 }

Write-Host "Keo model embedding bge-m3 (lan dau vai phut)..."
docker compose exec -T embedding ollama pull bge-m3
if ($LASTEXITCODE -ne 0) { Write-Host "!! Pull loi. Chay tay: docker compose exec embedding ollama pull bge-m3" }

$cl = if ($envmap["CHECKLIST_PORT"]) { $envmap["CHECKLIST_PORT"] } else { "8090" }
$wp = if ($envmap["WEB_PORT"]) { $envmap["WEB_PORT"] } else { "3000" }
Write-Host ""
Write-Host "==> Checklist: http://localhost:$cl"
Write-Host "==> ALICE app: http://localhost:$wp"
