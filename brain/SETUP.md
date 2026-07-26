# brain / SETUP — Dựng "não" (1 lệnh) + cấu hình trong app

Luồng đơn giản: **pull → 1 lệnh → mở checklist → set LLM key trong app → chạy INITIALIZATION từ Claude/Codex desktop**. Embedding `bge-m3` đã **bundled local** trong stack — không phải set tay.

## Yêu cầu
- **Docker** (Docker Desktop, hoặc Docker CE trong WSL) đang chạy.
- **Internet** cho lần đầu (launcher tự tải SAG `v1.3.0` + model `bge-m3`).
- (Để chạy INITIALIZATION) **Claude Desktop** hoặc **Codex Desktop**.

## Bước 1 — Một lệnh khởi động
```bash
# Windows
powershell -File knowledge\brain\stack\brain-up.ps1
# mac/Linux
bash knowledge/brain/stack/brain-up.sh
```
Chạy **một lần là xong**: launcher tự tạo `.env`, sinh `SAG_SECRET_KEY`, **tự clone SAG (ghim `v1.3.0`)**, tự chọn `BIND_ADDRESS` (WSL → `0.0.0.0`), build + chạy + pull `bge-m3`. **Không cần sửa `.env` tay.** Vận hành/log/dừng: [stack/README.md](stack/README.md).

## Bước 2 — Làm theo checklist trên app
Mở **http://localhost:8090** (trang checklist) và tick từng bước. Tóm tắt:
1. **http://localhost:3000** → nhập tên tạo identity (vd `Alice`).
2. **Settings → Models** → dán key LLM. Đề xuất **AIStudio/Gemini free** ([lấy key](https://aistudio.google.com/apikey)) hoặc OpenRouter free. *Embedding không cần set — đã bundled `bge-m3`.*
3. Tạo source thử + ingest 1 đoạn text + search → xác nhận embedding & LLM chạy.

> **Không mở được web UI (vd firewall Windows↔WSL)?** Khỏi cần UI — set LLM thẳng trong `brain/stack/.env` rồi chạy lại `brain-up`:
> ```env
> SAG_LLM_PROVIDER=gemini
> SAG_LLM_MODEL=gemini-2.0-flash
> SAG_LLM_API_KEY=<key AIStudio>
> ```

## Bước 3 — Nối "não" vào agent (MCP)

**Cách A — stdio bridge (KHUYÊN; chạy mọi nơi, KHÔNG cần network Windows↔WSL, không token).**
Agent chạy MCP server *bên trong container* rồi nối qua stdio → bỏ qua hết firewall/localhost.
- **Docker CE trong WSL** + agent Windows (Codex/Claude Desktop):
  ```json
  { "mcpServers": { "brain": {
      "command": "wsl",
      "args": ["-e","docker","exec","-i","alice-brain-api-1","python","-m","sag_api.mcp.server"] } } }
  ```
- **Docker Desktop / Linux / agent chạy trong WSL** (bỏ `wsl -e`):
  ```json
  { "mcpServers": { "brain": {
      "command": "docker",
      "args": ["exec","-i","alice-brain-api-1","python","-m","sag_api.mcp.server"] } } }
  ```
  - Codex: khai báo ở `~/.codex/config.toml` mục `[mcp_servers.brain]` (`command`/`args` như trên). Claude Desktop: `claude_desktop_config.json`. Điều kiện: stack đang chạy (container `alice-brain-api-1`).

**Cách B — HTTP MCP (chỉ khi Windows với tới được WSL, vd Docker Desktop / mirrored):** URL `http://localhost:8000/mcp/` + header `Authorization: Bearer <token>` (token: `POST /api/v1/auth/login`). VD Claude Code: `claude mcp add --transport http brain "http://localhost:8000/mcp/" --header "Authorization: Bearer <TOKEN>"`. Chi tiết: [../sub-agents/mcp.md](../sub-agents/mcp.md).

## Bước 4 — Chạy INITIALIZATION (từ desktop agent)
Mở Claude/Codex desktop trong repo project → *"Đọc và chạy knowledge/INITIALIZATION.md"*. Agent **tinh luyện** repo → `knowledge/` → ingest vào não (Bước 3b) → smoke → in vibe base-prompt.

## Đổi cấu hình sau này
- LLM/embedding: **Settings → Models** trên app (runtime, không cần rebuild).
- Đổi **embedding model** → nhớ `python knowledge/brain/sync/sync.py --rebuild` (tránh lệch chiều vector).

## Trục trặc
- **api `unhealthy` + `ValidationError: sag_language`:** SAG chỉ nhận `en`/`zh` (không có `vi`) → đặt `SAG_SAG_LANGUAGE=en` trong `.env` rồi chạy lại.
- **AI trả lời tiếng Trung:** SAG (gốc Trung) + model DeepSeek hay mặc định tiếng Trung. Vào **Settings → Assistant** đặt chỉ dẫn *"Always respond in Vietnamese"*, hoặc dùng **Gemini**; giữ `SAG_SAG_LANGUAGE=en` (cờ này chỉ `zh`/`en`, không có `vi` — và nó là ngôn ngữ *prompt* nội bộ, không phải ngôn ngữ *câu trả lời*). UI tiếng Trung → icon **文A** đổi giao diện.
- **Document FAILED (extract):** LLM chưa cấu hình / không phát JSON schema → set AIStudio-Gemini.
- **Embedding lỗi / search rỗng:** `docker compose logs embedding`; kiểm model đã pull: `docker compose exec embedding ollama list`.
- **`sync.py` không kết nối:** kiểm `docker compose ps` + `http://localhost:8000/api/v1/system/ready`.
- Chi tiết vận hành stack + chạy thủ công (không launcher): [stack/README.md](stack/README.md).
