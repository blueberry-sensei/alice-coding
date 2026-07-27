#!/usr/bin/env bash
# ALICE CODING — dựng brain stack bằng MỘT LỆNH (mac / Linux / WSL).
#
# Mặc định: KÉO IMAGE dựng sẵn về chạy. Không cần git, không cần source, không build gì.
# Tự động: tính BRAIN_ID riêng cho project, cấp cổng trống, sinh SAG_SECRET_KEY (ngoài repo),
# pull image + chạy NỀN + pull model embedding.
#
# MỖI PROJECT MỘT BRAIN: tên compose project suy từ đường dẫn kho tri thức, nên chạy song song
# nhiều project không đụng container, không đụng cổng, không chung dữ liệu.
#
# CHẾ ĐỘ DEV (chỉ dành cho người phát triển chính alice-brain / alice-core): đặt CẢ HAI
# ALICE_APP_PATH và ALICE_CORE_PATH trong file .env của brain (đường dẫn in ra ở cuối lệnh)
# → launcher build từ source trên máy thay vì dùng image đã publish.
set -euo pipefail

STACK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$STACK"

# Ghi toàn bộ output ra file: dựng stack lỗi ở bước nào (Docker, pull, build) thì còn cái mà
# đọc sau khi terminal đã đóng. Không có `tee` thì chạy tiếp, chỉ mất log.
LOG_DIR="$(cd "$STACK/.." && pwd)/.logs"
LOG_FILE="$LOG_DIR/brain-up.log"
if command -v tee >/dev/null 2>&1 && mkdir -p "$LOG_DIR" 2>/dev/null; then
  exec > >(tee -a "$LOG_FILE") 2>&1
else
  echo "[log] Cannot write the log file; console output only."
  LOG_FILE=""
fi

command -v node >/dev/null 2>&1 || {
  echo "!! Node 18+ is required HERE, in the environment this script runs in."
  if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
    echo "   You are inside WSL. Node installed on Windows does NOT count - Docker and this"
    echo "   launcher both run inside the distro. Install it here, for example:"
    echo "     curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
  fi
  exit 1
}

# Danh tính + cổng + secret: tính ở MỘT chỗ (brain-env.js) để launcher, cli.js và compose
# không bao giờ lệch nhau. File .env của brain nằm NGOÀI repo — xem BRAIN_ENV_FILE.
eval "$(node "$STACK/brain-env.js" --shell)"

COMPOSE_FILES=(-f "$STACK/compose.yaml")

if [ "$BRAIN_MODE" = "dev" ]; then
  # Kiểm tra thật, không tin lời khai trong .env: sai đường dẫn mà vẫn chạy tiếp thì lỗi
  # hiện ra ở giữa lúc build với thông báo khó hiểu.
  for pair in "ALICE_APP_PATH:apps/api" "ALICE_CORE_PATH:pyproject.toml"; do
    key="${pair%%:*}"; must="${pair##*:}"
    eval "dir=\$$key"
    [ -e "$dir/$must" ] || {
      echo "!! $key is wrong: $dir"
      echo "   That directory must contain '$must'. Fix it in: $BRAIN_ENV_FILE"
      exit 1
    }
  done
  COMPOSE_FILES+=(-f "$STACK/compose.dev.yaml")
  echo "DEV mode: building from local sources."
  echo "  ALICE_APP_PATH  = $ALICE_APP_PATH"
  echo "  ALICE_CORE_PATH = $ALICE_CORE_PATH"
  export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1   # additional_contexts cần BuildKit
fi

# BIND_ADDRESS mặc định 127.0.0.1, kể cả trên WSL (WSL2 chuyển tiếp localhost sẵn nên Windows
# vẫn mở được). Bản cũ tự bật 0.0.0.0 khi thấy WSL — đó là lỗ thật: brain nói HTTP TRẦN, mở ra
# ngoài nghĩa là API key gõ trên UI đi qua LAN ở dạng đọc được.
if [ "${BIND_ADDRESS:-127.0.0.1}" != "127.0.0.1" ]; then
  echo "!! WARNING: BIND_ADDRESS=$BIND_ADDRESS exposes the brain off this machine over PLAIN HTTP."
  echo "   API keys typed in the UI would travel the network in the clear. Trusted networks only."
fi

echo "BRAIN_ID     = $BRAIN_ID"
echo "Mode         = $BRAIN_MODE"
echo "BIND_ADDRESS = $BIND_ADDRESS"
echo "Ports        = web $WEB_PORT | api $API_PORT"

dc() { docker compose -p "$BRAIN_ID" "${COMPOSE_FILES[@]}" --env-file "$BRAIN_ENV_FILE" "$@"; }

if [ "$BRAIN_MODE" = "dev" ]; then
  dc up -d --build
else
  echo "Pulling ALICE images (a few minutes the first time)..."
  dc pull || {
    echo "!! Could not pull the images. Check your network, or they may not be published yet."
    echo "   Have the sources locally? Set ALICE_APP_PATH + ALICE_CORE_PATH in $BRAIN_ENV_FILE"
    echo "   to build from them instead of pulling."
    exit 1
  }
  dc up -d
fi

echo "Pulling the bge-m3 embedding model (a few minutes the first time)..."
dc exec -T embedding ollama pull bge-m3 \
  || echo "!! Model pull failed. Run it manually: npm run brain:pull"

echo ""
echo "==> ALICE app: http://localhost:${WEB_PORT}"
[ -n "$LOG_FILE" ] && echo "==> Stack build log: $LOG_FILE"
echo "==> API + engine log: $BRAIN_LOGS/sag-api.log"
echo "==> Brain config (OUTSIDE the repo, holds a secret - never commit): $BRAIN_ENV_FILE"

# WSL: VM tự tắt khi phiên launcher cuối cùng kết thúc → brain tắt theo. Bản cũ giữ VM sống
# bằng cách CHẶN terminal ở `logs -f`, nên đóng cửa sổ là mất brain và không làm được việc khác.
# Nay để lại một tiến trình nền trong distro: VM sống, terminal trả về ngay.
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  if ! pgrep -f "alice-brain-keepalive" >/dev/null 2>&1; then
    setsid nohup bash -c 'exec -a alice-brain-keepalive sleep infinity' >/dev/null 2>&1 < /dev/null &
    disown 2>/dev/null || true
  fi
  echo "==> WSL: a background process keeps the distro alive. Closing this terminal is fine."
  echo "    Stop it for good: npm run brain:down"
fi
