#!/usr/bin/env bash
# ALICE CODING — dựng brain stack bằng MỘT LỆNH (mac / Linux / WSL).
# Tự động: tạo .env, sinh SAG_SECRET_KEY, LẤY hai repo nguồn, chọn BIND_ADDRESS theo
# môi trường, build + chạy + pull model embedding. KHÔNG cần sửa .env tay.
#
# Nguồn build (cả hai đều tự lấy, KHÔNG cần chuẩn bị gì):
#   alice-brain -> fork ứng dụng (apps/api + apps/web)
#   alice-core  -> engine ALICE CORE (src/alicecore)
# Đang phát triển chính hai repo đó? Đặt ALICE_APP_PATH / ALICE_CORE_PATH trong
# .env để build từ bản trên máy thay vì bản trên GitHub.
set -euo pipefail

STACK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$STACK"

[ -f .env ] || cp .env.example .env
set -a; . ./.env; set +a

APP_REPO="${ALICE_APP_REPO:-https://github.com/blueberry-sensei/alice-brain.git}"
CORE_REPO="${ALICE_CORE_REPO:-https://github.com/blueberry-sensei/alice-core.git}"
APP_REF="${ALICE_APP_REF:-main}"
CORE_REF="${ALICE_CORE_REF:-main}"

# SAG_SECRET_KEY (sinh nếu thiếu)
if [ -z "${SAG_SECRET_KEY:-}" ]; then
  SAG_SECRET_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  sed -i.bak "s|^SAG_SECRET_KEY=.*|SAG_SECRET_KEY=${SAG_SECRET_KEY}|" .env && rm -f .env.bak
  echo "Đã sinh SAG_SECRET_KEY."
fi

abspath() {
  local p="${1:-$2}"
  case "$p" in /*|?:*) : ;; *) p="$STACK/$p" ;; esac
  [ "${3:-}" = "create" ] && mkdir -p "$p"
  ( cd "$p" 2>/dev/null && pwd ) || echo "$p"
}

# Trỏ tới bản trên máy nếu .env khai báo; nếu không thì clone (ghim ref) vào ./<dir>.
# $1=tên biến  $2=repo  $3=ref  $4=thư mục đích  $5=file/thư mục bắt buộc phải có  $6=mô tả
resolve_source() {
  local key="$1" repo="$2" ref="$3" dir="$4" must="$5" what="$6" raw abs
  eval "raw=\${$key:-}"
  if [ -n "$raw" ]; then
    abs="$(abspath "$raw" "$raw")"
    [ -e "$abs/$must" ] || {
      echo "!! $key sai: $abs"
      echo "   Thư mục này phải chứa '$must' ($what)."
      exit 1
    }
  else
    abs="$STACK/$dir"
    if [ ! -e "$abs/$must" ]; then
      echo "Lấy $dir ($ref)..."
      rm -rf "$abs"
      git clone --depth 1 --branch "$ref" "$repo" "$abs" \
        || { echo "!! Không clone được $repo (kiểm mạng / git)."; exit 1; }
    elif [ -d "$abs/.git" ]; then
      # Thư mục do launcher tự clone → LÀM MỚI. Không có bước này thì mọi lần chạy
      # sau đều build từ source cũ và bản cập nhật không bao giờ tới được người dùng.
      # `reset --hard` an toàn ở đây vì đây là bản sao chỉ-đọc do launcher quản lý;
      # ai muốn sửa source thì dùng ALICE_APP_PATH / ALICE_CORE_PATH (nhánh trên).
      echo "Cập nhật $dir ($ref)..."
      if git -C "$abs" fetch --depth 1 origin "$ref" >/dev/null 2>&1; then
        git -C "$abs" reset --hard FETCH_HEAD >/dev/null 2>&1 \
          || echo "!! Không đặt lại được $dir về $ref — dùng bản đang có."
      else
        echo "!! Không fetch được $dir (kiểm mạng) — dùng bản đang có."
      fi
    fi
    [ -e "$abs/$must" ] || {
      echo "!! $dir tải về nhưng thiếu '$must' — repo nguồn có thể đã đổi cấu trúc."
      exit 1
    }
  fi
  eval "export $key=\"$abs\""
}

command -v git >/dev/null 2>&1 || { echo "!! Cần git để lấy source."; exit 1; }
resolve_source ALICE_APP_PATH  "$APP_REPO"  "$APP_REF"  "alice-brain" "apps/api"       "fork ứng dụng ALICE"
resolve_source ALICE_CORE_PATH "$CORE_REPO" "$CORE_REF" "alice-core"  "pyproject.toml" "engine ALICE CORE"

export BRAIN_DATA="$(abspath "${BRAIN_DATA:-}" "../.sag-data" create)"
export SAG_SECRET_KEY

# BIND_ADDRESS: WSL cần 0.0.0.0 để mở từ Windows; nơi khác 127.0.0.1 (trừ khi .env ép sẵn)
if [ -z "${BIND_ADDRESS:-}" ]; then
  if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
    BIND_ADDRESS=0.0.0.0; echo "Phát hiện WSL → BIND_ADDRESS=0.0.0.0"
  else
    BIND_ADDRESS=127.0.0.1
  fi
fi
export BIND_ADDRESS

echo "ALICE_APP_PATH  = $ALICE_APP_PATH"
echo "ALICE_CORE_PATH = $ALICE_CORE_PATH"
echo "BRAIN_DATA      = $BRAIN_DATA"
echo "BIND_ADDRESS    = $BIND_ADDRESS"
export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1   # additional_contexts cần BuildKit
docker compose --env-file .env up -d --build

echo "Kéo model embedding bge-m3 (lần đầu vài phút)..."
docker compose exec -T embedding ollama pull bge-m3 \
  || echo "!! Pull model lỗi. Chạy tay: docker compose exec embedding ollama pull bge-m3"

echo ""
echo "==> Checklist: http://localhost:${CHECKLIST_PORT:-8090}"
echo "==> ALICE app: http://localhost:${WEB_PORT:-3000}"

# WSL: VM tự tắt NGAY khi phiên launcher kết thúc → brain tắt theo. Vì vậy trên WSL,
# launcher GIỮ phiên sống bằng cách theo dõi log (chặn) → VM sống → localhost dùng được.
# (mac/Linux/Docker Desktop: bỏ qua, launcher thoát bình thường vì daemon tự sống.)
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "  ✅ BRAIN ĐANG CHẠY — GIỮ CỬA SỔ NÀY MỞ (nó giữ WSL + brain sống)."
  echo "  🌐 Mở trên trình duyệt Windows:  http://localhost:${WEB_PORT:-3000}"
  echo "  ⏹  Ctrl+C = TẮT brain."
  echo "════════════════════════════════════════════════════════════════"
  echo ""
  exec docker compose --env-file .env logs -f 2>/dev/null || exec sleep infinity
fi
