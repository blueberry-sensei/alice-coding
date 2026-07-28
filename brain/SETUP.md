# brain / SETUP — Dựng "não" (1 lệnh) + cấu hình trong app

Luồng đơn giản: **pull → 1 lệnh → thêm provider LLM trong app → chạy INITIALIZATION từ Claude/Codex desktop**. Embedding `bge-m3` đã **bundled local** trong stack — không phải set tay.

## Yêu cầu
- **Docker** (Docker Desktop, hoặc Docker CE trong WSL) đang chạy.
- **Internet** cho lần đầu (kéo image ALICE + model `bge-m3`).
- (Để chạy INITIALIZATION) **Claude Desktop** hoặc **Codex Desktop**.

## Bước 1 — Một lệnh khởi động
```bash
npm run brain
```
Chạy **một lần là xong**: launcher tự chọn script đúng môi trường, tính `BRAIN_ID` riêng cho project, cấp hostname `<BRAIN_ID>.localhost` + cổng trống, sinh `SAG_SECRET_KEY` (lưu **ngoài repo**), **kéo image dựng sẵn** + chạy **nền** + pull `bge-m3`. **Không cần git, không cần source, không cần sửa `.env` tay.**

> **Mỗi project một brain.** Máy đã có brain của project khác thì cứ chạy tiếp — launcher tự né cổng và tự tách dữ liệu. `npm run brain:list` cho biết máy đang có brain nào.
>
> **URL và cổng không gõ tay.** Mỗi project có URL riêng, ví dụ
> `http://alice-my-project-a1b2c3.localhost:3000`; lấy URL thật bằng `npm run brain:status`.
> `.localhost` là loopback, không cần DNS/hosts file và không phơi brain ra mạng.

Vận hành/log/dừng: [stack/README.md](stack/README.md).

## Bước 2 — Cấu hình LLM trên app
Mở địa chỉ project mà launcher in ra rồi làm ba việc:
1. **`http://<BRAIN_ID>.localhost:<WEB_PORT>`** → nhập tên tạo identity (vd `Alice`).
2. **Settings → Models** → thêm provider LLM. Đề xuất **AIStudio/Gemini free** ([lấy key](https://aistudio.google.com/apikey)) hoặc OpenRouter free. *Embedding không cần set — đã bundled `bge-m3`.*
3. Tạo source thử + ingest 1 đoạn text + search → xác nhận embedding & LLM chạy.

### Nhiều provider, tự chuyển nhà khi hết quota

Thêm được nhiều provider và xếp **thứ tự ưu tiên**. Hệ thống luôn bắt đầu từ ưu tiên cao nhất còn khoẻ:

| Tình huống | Xử lý |
| --- | --- |
| Timeout / kết nối / lỗi 5xx | Thử lại **cùng** provider (backoff) |
| 429 / hết quota | Chuyển ngay sang provider kế, cho provider này nghỉ một lúc |
| Sai API key / model không tồn tại | Tắt provider đó, chuyển nhà, **báo rõ lý do** |
| Request không hợp lệ | Dừng luôn — đổi nhà cũng lỗi y vậy |

Cần ép backend cụ thể (vd OpenRouter → `deepinfra/fp4`) thì điền vào ô **extra body**:
`{"provider": {"order": ["deepinfra/fp4"], "allow_fallbacks": false}}`.

Mọi lần gọi thất bại đều nằm trong **Settings → Models → lịch sử gọi**: provider nào, lỗi loại gì, lúc nào. Không có thất bại im lặng.

> **API key nằm ở đâu?** Trong DB của brain, **đã mã hoá** bằng khoá dẫn xuất từ `SAG_SECRET_KEY`. Không có key nào nằm trong file thuộc repo, nên không sợ commit nhầm. Đổi `SAG_SECRET_KEY` = mất key đã lưu, phải nhập lại (tri thức không ảnh hưởng).
>
> **`.env` không còn cấu hình LLM.** Các biến `SAG_LLM_*` của bản cũ đã bỏ; còn sót trong `.env` thì xoá đi cho khỏi tưởng là đã cấu hình.

## Bước 3 — Nối "não" vào agent (MCP)

**Cách A — stdio bridge (KHUYÊN; chạy mọi nơi, KHÔNG cần network Windows↔WSL, không token).**
Agent chạy MCP server *bên trong container* rồi nối qua stdio → bỏ qua hết firewall/localhost.
- **Docker CE trong WSL** + agent Windows (Codex/Claude Desktop):
  ```json
  { "mcpServers": { "brain": {
      "command": "wsl",
      "args": ["-e","docker","exec","-i","<BRAIN_ID>-api-1","python","-m","sag_api.mcp.server"] } } }
  ```
- **Docker Desktop / Linux / agent chạy trong WSL** (bỏ `wsl -e`):
  ```json
  { "mcpServers": { "brain": {
      "command": "docker",
      "args": ["exec","-i","<BRAIN_ID>-api-1","python","-m","sag_api.mcp.server"] } } }
  ```
  - Codex: khai báo ở `~/.codex/config.toml` mục `[mcp_servers.brain]` (`command`/`args` như trên). Claude Desktop: `claude_desktop_config.json`. Điều kiện: stack đang chạy (container `<BRAIN_ID>-api-1`).

**Cách B — HTTP MCP (chỉ khi Windows với tới được WSL, vd Docker Desktop / mirrored):** dùng
URL API mà `npm run brain:status` in ra, thêm `/mcp/`, cùng header
`Authorization: Bearer <token>` (token: `POST /api/v1/auth/login`). Chi tiết:
[../sub-agents/mcp.md](../sub-agents/mcp.md).

## Bước 4 — Chạy INITIALIZATION (từ desktop agent)
Mở Claude/Codex desktop trong repo project → *"Đọc và chạy knowledge/INITIALIZATION.md"*. Agent **tinh luyện** repo → `knowledge/` → ingest vào não (Bước 3b) → smoke → in vibe base-prompt.

## Đổi cấu hình sau này
- LLM/embedding: **Settings → Models** trên app (runtime, không cần rebuild).
- Đổi **embedding model** → nhớ `npm run sync:rebuild` (tránh lệch chiều vector).

## Log — tìm ở đâu khi có lỗi

Mọi tầng đều ghi ra file local, không chỉ ra terminal:

| Log | Đường dẫn | Gồm gì |
| --- | --- | --- |
| API + engine | `brain/.logs/api/sag-api.log` | Request, ingest, extract, mọi lần gọi provider, traceback. Xoay vòng 20 MB × 5 bản |
| Dựng stack | `brain/.logs/brain-up.log` | Toàn bộ output của launcher (clone, build, pull model) |
| Sync tri thức | `brain/.logs/sync.log` | Từng file được ingest/update/delete, kèm traceback nếu lỗi |
| Container | `npm run brain:logs` | stdout của cả ba container |

Mỗi dòng log của API có `request_id`; lấy id đó lần được cả chuỗi xử lý một request qua các tầng.

## Trục trặc
- **api `unhealthy` + `ValidationError: sag_language`:** cờ này chỉ nhận `en` hoặc `vi` → đặt `SAG_SAG_LANGUAGE=en` trong `.env` rồi chạy lại `npm run brain`.
- **AI trả lời sai ngôn ngữ:** vào **Settings → Assistant** đặt chỉ dẫn *"Always respond in Vietnamese"*. `SAG_SAG_LANGUAGE` là ngôn ngữ **prompt trích xuất** nội bộ, không phải ngôn ngữ câu trả lời — giữ `en` cho model bám JSON schema ổn định.
- **Document FAILED (extract):** chưa có provider LLM nào, hoặc model không phát được JSON schema → thêm provider ở **Settings → Models** và xem **lịch sử gọi** để biết provider nào fail vì gì.
- **Embedding lỗi / search rỗng:** embedding **không** đổi nhà khi lỗi (đổi model = đổi không gian vector), nên nó thử lại rồi báo lỗi thẳng và để document ở trạng thái FAILED. Xem `npm run brain:logs`; kiểm model đã pull: `npm run brain:status`.
- **Sync không kết nối:** `npm run brain:status`, rồi mở URL API được in ra + `/api/v1/system/ready`.
- Chi tiết vận hành stack: [stack/README.md](stack/README.md).

> `<BRAIN_ID>` là danh tính brain của **project này** — nó cũng đặt tên hostname và knowledge
> source (`<BRAIN_ID>-knowledge`). Đừng gõ tay: lấy nguyên khối cấu hình bằng `npm run mcp`, và
> lấy URL bằng `npm run brain:status`.
