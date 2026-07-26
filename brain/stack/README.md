# brain/stack — Khởi động "não" bằng 1 lệnh

Stack Docker gói sẵn: **SAG** (api + web) + **embedding `bge-m3` local** (bundled) + **trang checklist**. Mục tiêu: pull ALICE CODING về, chạy 1 lệnh, rồi cấu hình LLM ngay trên app.

## Chạy
```bash
# Windows
powershell -File knowledge\brain\stack\brain-up.ps1
# mac/Linux
bash knowledge/brain/stack/brain-up.sh
```
Chạy **một lần là xong**: tạo `.env` → sinh `SAG_SECRET_KEY` → **tự clone SAG (ghim `v1.3.0`) vào `./sag`** → chọn `BIND_ADDRESS` (WSL → `0.0.0.0`) → build → pull `bge-m3`. Sau đó mở **http://localhost:8090** (checklist) và **http://localhost:3000** (app SAG).

> Muốn TÁI DÙNG bản SAG đã có (đỡ tải): đặt `SAG_PATH=/đường/dẫn/SAG` trong `.env`. Để trống thì launcher tự clone.

## Chạy thủ công (nếu không dùng launcher)
Trong `knowledge/brain/stack/`, đặt `SAG_PATH` + `BRAIN_DATA` **tuyệt đối** + `SAG_SECRET_KEY` trong `.env`, rồi:
```bash
docker compose --env-file .env up -d --build
docker compose exec embedding ollama pull bge-m3
```

## Thành phần & cổng
| Service | Vai trò | Cổng (host, chỉ 127.0.0.1) |
|---|---|---|
| `web` | App SAG (Settings → Models để set LLM) | `3000` |
| `api` | Backend SAG + MCP (`/mcp/`) + REST | `8000` |
| `embedding` | `bge-m3` local (Ollama, OpenAI-compatible) | nội bộ `11434` |
| `checklist` | Trang hướng dẫn từng bước | `8090` |

## Dữ liệu & vòng đời
- Toàn bộ "não" nằm ở **`BRAIN_DATA`** (mặc định `knowledge/brain/.sag-data`, đã gitignore) — **bind-mount**, sống sót qua `docker compose down -v` / prune.
- Dừng: `docker compose down` (giữ data). Xem log: `docker compose logs -f api embedding`.
- Mất data vẫn dựng lại được từ file: `python knowledge/brain/sync/sync.py --rebuild`.

## Tương thích: WSL (Docker CE) vs Docker Desktop

Stack gồm **toàn container Linux** nên **giống hệt** trên cả hai máy. Chỉ 2 điểm phụ thuộc máy:

1. **Chạy launcher đúng môi trường của daemon:**
   - **Docker CE trong WSL** (không có `docker` trên Windows PATH) → chạy `bash brain-up.sh` **bên trong WSL**.
   - **Docker Desktop** (`docker` có trên Windows) → chạy `brain-up.ps1` (PowerShell) *hoặc* `brain-up.sh` (WSL/Git Bash) — tùy ý.
   - Nguyên tắc: launcher tính path theo môi trường nó chạy → **đừng trộn** (đừng chạy `.ps1` ở Windows khi daemon chỉ nằm trong WSL).
2. **`.env` là per-máy** (đã gitignore) → mỗi máy tự đặt `SAG_PATH`. **Khuyên dùng submodule `./sag` (đường dẫn tương đối)** → khỏi path tuyệt đối, chạy y hệt cả hai. Nếu để tuyệt đối: WSL dùng path Linux (`/mnt/d/...` hoặc `~/...`), Desktop+PowerShell dùng `D:/...`.

**Hiệu năng (WSL CE):** để repo + `BRAIN_DATA` trong **filesystem của WSL** (`~/...`) thay vì `/mnt/d/...` (bind-mount 9p chậm, nhất là model Ollama vài GB).

**Line-ending:** repo có `.gitattributes` ép `*.sh` = **LF** để bash trong WSL không lỗi `\r`.

**GPU (tùy chọn):** CPU chạy mặc định cả hai. Muốn tăng tốc embedding thì bật GPU cho service `embedding` (Desktop: WSL2 GPU; WSL CE: nvidia-container-toolkit).

## Mở được từ trình duyệt Windows khi Docker CE chạy trong WSL

**Nguyên nhân thật (đã xác minh, KHÔNG phải firewall):** `localhost` từ Windows tới WSL chạy bình thường (`curl.exe http://localhost:8090` → 200). Vấn đề duy nhất: **WSL VM tự tắt khi không còn phiên nào mở** → docker + brain tắt theo → lúc đó mở localhost mới lỗi.

**→ Cách đúng: giữ WSL sống khi dùng brain.**
1. **Nhanh:** mở 1 cửa sổ WSL (`wsl`) và để yên (hoặc chạy `docker compose logs -f` trong đó). WSL còn sống → `http://localhost:3000` mở thẳng trên Windows.
2. **Bền:** để Docker CE tự chạy qua **systemd** — `/etc/wsl.conf` thêm `[boot]` + `systemd=true`, rồi `sudo systemctl enable --now docker` — để daemon giữ VM sống.

*(`enable-wsl-localhost.ps1` / mirrored networking chỉ cần khi máy thật sự chặn localhost-forwarding — hiếm, đa số KHÔNG cần.)*

## Ghi chú
- Chưa live-test trên máy này — nếu vấp, xem log service tương ứng; đổi embedding server (vd TEI/Infinity) chỉ là đổi service `embedding` + `SAG_EMBEDDING_BASE_URL`.
- Đừng expose cổng ra internet (SAG single-user, local).
