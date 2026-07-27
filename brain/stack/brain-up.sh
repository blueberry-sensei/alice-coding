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
  echo "[log] Không ghi được log ra file; chỉ còn console."
  LOG_FILE=""
fi

command -v node >/dev/null 2>&1 || { echo "!! Cần Node 18+ (brain-env.js tính danh tính brain)."; exit 1; }

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
      echo "!! $key sai: $dir"
      echo "   Thư mục này phải chứa '$must'. Sửa trong: $BRAIN_ENV_FILE"
      exit 1
    }
  done
  COMPOSE_FILES+=(-f "$STACK/compose.dev.yaml")
  echo "Chế độ DEV: build từ source trên máy."
  echo "  ALICE_APP_PATH  = $ALICE_APP_PATH"
  echo "  ALICE_CORE_PATH = $ALICE_CORE_PATH"
  export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1   # additional_contexts cần BuildKit
fi

# BIND_ADDRESS mặc định 127.0.0.1, kể cả trên WSL (WSL2 chuyển tiếp localhost sẵn nên Windows
# vẫn mở được). Bản cũ tự bật 0.0.0.0 khi thấy WSL — đó là lỗ thật: brain nói HTTP TRẦN, mở ra
# ngoài nghĩa là API key gõ trên UI đi qua LAN ở dạng đọc được.
if [ "${BIND_ADDRESS:-127.0.0.1}" != "127.0.0.1" ]; then
  echo "!! CẢNH BÁO: BIND_ADDRESS=$BIND_ADDRESS → brain mở ra ngoài máy qua HTTP KHÔNG mã hoá."
  echo "   API key nhập trên UI sẽ đi qua mạng ở dạng đọc được. Chỉ dùng trên mạng tin cậy."
fi

echo "BRAIN_ID     = $BRAIN_ID"
echo "Chế độ       = $BRAIN_MODE"
echo "BIND_ADDRESS = $BIND_ADDRESS"
echo "Cổng         = web $WEB_PORT · api $API_PORT · checklist $CHECKLIST_PORT"

dc() { docker compose -p "$BRAIN_ID" "${COMPOSE_FILES[@]}" --env-file "$BRAIN_ENV_FILE" "$@"; }

if [ "$BRAIN_MODE" = "dev" ]; then
  dc up -d --build
else
  echo "Kéo image ALICE (lần đầu vài phút)..."
  dc pull || {
    echo "!! Không kéo được image. Kiểm mạng, hoặc image chưa được publish."
    echo "   Có source trên máy? Đặt ALICE_APP_PATH + ALICE_CORE_PATH trong $BRAIN_ENV_FILE"
    echo "   để build từ đó thay vì kéo image."
    exit 1
  }
  dc up -d
fi

echo "Kéo model embedding bge-m3 (lần đầu vài phút)..."
dc exec -T embedding ollama pull bge-m3 \
  || echo "!! Pull model lỗi. Chạy tay: npm run brain:pull"

echo ""
echo "==> Checklist: http://localhost:${CHECKLIST_PORT}"
echo "==> ALICE app: http://localhost:${WEB_PORT}"
[ -n "$LOG_FILE" ] && echo "==> Log dựng stack: $LOG_FILE"
echo "==> Log API + engine: $BRAIN_LOGS/sag-api.log"
echo "==> Cấu hình brain (NGOÀI repo, có secret — đừng commit): $BRAIN_ENV_FILE"

# WSL: VM tự tắt khi phiên launcher cuối cùng kết thúc → brain tắt theo. Bản cũ giữ VM sống
# bằng cách CHẶN terminal ở `logs -f`, nên đóng cửa sổ là mất brain và không làm được việc khác.
# Nay để lại một tiến trình nền trong distro: VM sống, terminal trả về ngay.
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  if ! pgrep -f "alice-brain-keepalive" >/dev/null 2>&1; then
    setsid nohup bash -c 'exec -a alice-brain-keepalive sleep infinity' >/dev/null 2>&1 < /dev/null &
    disown 2>/dev/null || true
  fi
  echo "==> WSL: đã để tiến trình nền giữ distro sống. Đóng terminal này vẫn OK."
  echo "    Tắt hẳn: npm run brain:down"
fi
