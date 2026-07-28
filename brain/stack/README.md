# brain/stack — Khởi động "não" bằng 1 lệnh

Stack Docker gói sẵn: **ALICE** (api + web) + **embedding `bge-m3` local** (bundled). Mục tiêu: pull ALICE CODING về, chạy 1 lệnh, rồi cấu hình LLM ngay trên app.

## Chạy
```bash
npm run brain
```
Launcher tự chọn script đúng môi trường. Chạy **một lần là xong**: tính `BRAIN_ID` cho project → cấp cổng trống → sinh `SAG_SECRET_KEY` (lưu **ngoài repo**) → **kéo image dựng sẵn** → chạy **nền** → pull `bge-m3`. Cuối cùng launcher in ra đúng URL kèm cổng đã cấp.

Không cần `git`, không cần source, không phải build gì. Chỉ cần Docker và Node.

> Cổng **không cố định**. Project đầu tiên trên máy thường vẫn được 3000/8000; project sau tự né sang cổng trống. Lấy cổng thật bằng `npm run brain:status`, xem toàn máy bằng `npm run brain:list`.

### Mỗi project một brain

`BRAIN_ID` suy từ **đường dẫn tuyệt đối của kho tri thức**, rồi được truyền cho compose qua `-p`.
Vì vậy container, network và named volume của mỗi project đều mang tiền tố riêng — hai project
chạy song song không đụng nhau và **không có đường nào nhìn thấy dữ liệu của nhau**.

### Hai chế độ

| Chế độ | Khi nào | Làm gì |
|---|---|---|
| `image` (mặc định) | `ALICE_APP_PATH` để trống | Kéo `ghcr.io/<owner>/alice-brain-api` + `-web` về chạy |
| `dev` | Đặt **cả hai** `ALICE_APP_PATH` và `ALICE_CORE_PATH` trong `.env` của brain | Chồng `compose.dev.yaml`, build từ source trên máy, tag `…:dev-<BRAIN_ID>` |

`npm run brain:status` in ra đang ở chế độ nào. Đổi image nguồn (registry riêng, tag cố định)
bằng `ALICE_IMAGE_API` / `ALICE_IMAGE_WEB` trong `.env` của brain — không bị khoá vào GHCR.

Engine ALICE CORE vào image `api` qua stage `alicecore`, và stage đó được thoả bằng **một trong
hai** cách cho ra cây thư mục giống hệt nhau: image `ghcr.io/<owner>/alice-core` (CI) hoặc thư
mục local ghi đè bằng `--build-context` (dev). Nhờ vậy không có chuyện "CI build được mà máy
mình thì không".

> **Cổng API không nướng vào image.** Web đọc cổng lúc chạy (`SAG_PUBLIC_API_PORT` → nhúng vào
> HTML → `lib/api.ts`), nên cùng một image dùng cho mọi project mà web của project này không
> bao giờ gọi nhầm sang API của project khác.

### Secret nằm ở đâu

`SAG_SECRET_KEY` vừa ký JWT vừa là gốc dẫn xuất khoá mã hoá **mọi API key** trong DB, nên nó
**không** được nằm trong cây repo. File `.env` của brain ở:

| OS | Đường dẫn |
|---|---|
| Windows | `%LOCALAPPDATA%\alice-brain\<BRAIN_ID>\.env` |
| mac / Linux | `${XDG_STATE_HOME:-~/.local/state}/alice-brain/<BRAIN_ID>/.env` |

Repo chỉ còn `.env.example` làm tài liệu. Bản cài cũ có `brain/stack/.env` sẽ được launcher
**chuyển sang chỗ mới rồi xoá bản trong repo**, giữ nguyên giá trị (đổi `SAG_SECRET_KEY` là mất
sạch API key đã lưu).

## Vận hành
```bash
npm run brain:status     # trạng thái container
npm run brain:logs       # log của cả stack
npm run brain:restart    # khởi động lại
npm run brain:down       # tắt (giữ data)
```

## Thành phần & cổng
| Service | Vai trò | Cổng (host, chỉ 127.0.0.1) |
|---|---|---|
| `web` | App ALICE (Settings → Models để thêm provider LLM) | `3000` |
| `api` | Backend + MCP (`/mcp/`) + REST | `8000` |
| `embedding` | `bge-m3` local (Ollama, OpenAI-compatible) | nội bộ `11434` |

## Dữ liệu & vòng đời
- Toàn bộ "não" (SQLite + LanceDB + upload) nằm trong **named volume** `<BRAIN_ID>_sagdata`, model Ollama ở `<BRAIN_ID>_ollama`. Không còn file dữ liệu nào trong cây repo → không thể lỡ tay commit, và copy thư mục project đi nơi khác không kéo theo "não".
- Xem/sao lưu: `docker volume ls`, hoặc `docker run --rm -v <BRAIN_ID>_sagdata:/d -v "$PWD":/out alpine tar czf /out/brain-backup.tgz -C /d .`
- `npm run uninstall:yes` gỡ **sạch**: container, network, volume, image của brain
  này, image mồ côi, **và build cache của Docker** — phần cuối thường là vài chục GB và là lý do
  "gỡ rồi mà đĩa vẫn đầy". Build cache dùng chung cả máy nên nếu đang có project Docker khác thì
  thêm `--keep-cache` để giữ (chỉ mất tốc độ build lần sau, không mất dữ liệu).
- Dừng: `npm run brain:down` (giữ data). Xem log container: `npm run brain:logs`.
- Mất data vẫn dựng lại được từ file: `npm run sync:rebuild`.

## Log ra file
| Log | Đường dẫn | Gồm gì |
|---|---|---|
| API + engine | `brain/.logs/api/sag-api.log` | Request (có `request_id`), ingest, extract, mọi lần gọi provider LLM, traceback. Xoay vòng 20 MB × 5 bản |
| Dựng stack | `brain/.logs/brain-up.log` | Output của launcher: clone, build, pull model |
| Sync tri thức | `brain/.logs/sync.log` | File nào ingest/update/delete, traceback nếu lỗi |

Đổi chỗ ghi / kích thước: `SAG_LOG_DIR`, `SAG_LOG_FILE_MAX_MB`, `SAG_LOG_FILE_BACKUPS` trong `.env`.

## Tương thích: WSL (Docker CE) vs Docker Desktop

Stack gồm **toàn container Linux** nên **giống hệt** trên cả hai máy. Chỉ 2 điểm phụ thuộc máy:

1. **Chạy launcher đúng môi trường của daemon:**
   - **Docker CE trong WSL** (không có `docker` trên Windows PATH) → chạy `npm run brain` **bên trong WSL**.
   - **Docker Desktop** (`docker` có trên Windows) → chạy `npm run brain` ở đâu cũng được.
   - Nguyên tắc: launcher tính path theo môi trường nó chạy → **đừng trộn** (đừng chạy từ Windows khi daemon chỉ nằm trong WSL).
2. **`.env` của brain là per-máy và nằm NGOÀI repo.** Mặc định để trống là tốt nhất — launcher kéo image dựng sẵn. Chỉ người phát triển chính alice-brain/alice-core mới cần `ALICE_APP_PATH` + `ALICE_CORE_PATH` (phải đặt **cả hai**): WSL dùng path Linux (`/mnt/d/...` hoặc `~/...`), Desktop+PowerShell dùng `D:/...`.

**Hiệu năng (WSL CE):** để repo trong **filesystem của WSL** (`~/...`) thay vì `/mnt/d/...` (bind-mount 9p chậm). Dữ liệu não nay nằm trong named volume nên không còn dính bind-mount 9p.

**Line-ending:** repo có `.gitattributes` ép `*.sh` = **LF** để bash trong WSL không lỗi `\r`.

**GPU (tùy chọn):** CPU chạy mặc định cả hai. Muốn tăng tốc embedding thì bật GPU cho service `embedding` (Desktop: WSL2 GPU; WSL CE: nvidia-container-toolkit).

## Mở được từ trình duyệt Windows khi Docker CE chạy trong WSL

**Nguyên nhân thật (đã xác minh, KHÔNG phải firewall):** `localhost` từ Windows tới WSL chạy
bình thường. Vấn đề duy nhất: **WSL VM tự tắt khi không còn phiên nào mở** → docker + brain tắt
theo → lúc đó mở localhost mới lỗi.

**Launcher đã tự xử lý:** `npm run brain` để lại một tiến trình nền (`alice-brain-keepalive`)
trong distro nên VM sống tiếp và **terminal được trả về ngay** — không phải giữ cửa sổ nào mở.
Tắt hẳn: `npm run brain:down`.

> ⚠️ **Node phải cài BÊN TRONG WSL.** Docker nằm trong distro nên launcher cũng chạy ở đó;
> Node cài trên Windows không dùng được. Cài trong WSL:
> `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs`

Muốn bền hơn nữa thì cho Docker CE chạy qua **systemd**: `/etc/wsl.conf` thêm `[boot]` +
`systemd=true`, rồi `sudo systemctl enable --now docker`.

## Ghi chú
- Nếu vấp, xem `sag-api.log` (bảng Log ở trên) rồi tới `npm run brain:logs`; đổi embedding server (vd TEI/Infinity) chỉ là đổi service `embedding` + `SAG_EMBEDDING_BASE_URL`.
- Đừng expose cổng ra internet (single-user, local).
