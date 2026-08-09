# brain / SYNC — Đồng bộ file → não (chống trùng)

SAG **không có dedup/idempotency**: nếu ingest mù một file đã sửa, nó tạo **document + chunk TRÙNG**. `sync.py` giải việc này bằng cách tự giữ map `file → document_id + sha256`.

Sau một lượt có thay đổi, sync tự ghi event **Knowledge write** vào Settings → Telemetry với source,
danh sách file tạo/cập nhật/xoá và tổng `+ / ~ / -`. Event chỉ được gửi sau khi ingest request hoàn
tất và `.sync-state.json` đã lưu; sửa Markdown trên host mà chưa sync thì chưa phải tri thức trong
Brain. Lượt không có diff không tạo event.

## Gate: verify chạy TRƯỚC, hỏng thì không sync

`sync.py` gọi [`tools/verify.py`](../tools/verify.py) trước mọi thứ và **dừng nếu còn ERROR**.

> Vì sao đặt gate ở đây: sync là **chỗ nghẽn bắt buộc** của cả hệ thống — không sync thì não không có tri thức mới, agent mất recall. Đặt kiểm tra tại đây khiến kỷ luật trở thành **bắt buộc** mà vẫn **không** phải khoá vào hook riêng của agent nào (Claude Code hook, Codex hook…). Đây là lớp phòng thủ duy nhất sống **ngoài** context của model, nên nó vẫn còn nguyên sau auto-compact.

Sync khi kho tri thức đang hỏng còn tệ hơn không sync: nó nhồi trang mồ côi, citation chết và entry trùng ID vào não, làm recall **tệ đi**.

`--no-verify` tồn tại để gỡ lỗi. Dùng nó để né gate là vi phạm `ALICE.md` mục 6.

## Cách hoạt động
- **State** `brain/.sync-state.json` (gitignore): `{ "schema": 2, "source_id": …, "files": { "wiki/payments.md": {"document_id": …, "sha256": …} } }`.
- Với từng file `.md` trong phạm vi:
  - **Mới** (chưa có trong state) → `ingest` → ghi map.
  - **Đổi** (sha256 khác) → **delete document cũ + ingest lại** → cập nhật hash. *(Không dùng `/reprocess` của SAG vì nó đọc bản copy nội bộ, không phải file sống.)*
  - **Trùng hash** → bỏ qua (rẻ).
- File có trong state nhưng **mất trên đĩa** → delete document + xoá khỏi state.

### Schema của state
`schema` được version hoá. State cũ hơn script → `sync.py` **dừng và yêu cầu `--rebuild`**, thay vì diễn giải sai map rồi đẻ ra document trùng. Rebuild luôn an toàn vì file `knowledge/` mới là source-of-truth.

## Phạm vi (mặc định)
- **Include:** `wiki/`, `mistakes/`, `decisions/`, `context/`, `changelog/` (chỉnh qua `BRAIN_INCLUDE`).
- **Exclude:** file chứa `_TEMPLATE.md` (chỉnh qua `BRAIN_EXCLUDE`).
- **KHÔNG** đụng source code, cũng **không** đụng file luật/hướng dẫn thuần template (`ALICE.md`, `ALICE.project.md`, `INITIALIZATION.md`, `README`, `UPGRADE`, `MIGRATIONS`, `prompts`).

## Chạy
```bash
npm run sync                 # đồng bộ incremental (chỉ file đổi)
npm run sync:rebuild         # xoá sạch source + ingest lại toàn bộ
npm run sync:no-verify       # bỏ gate — chỉ khi gỡ lỗi
npm run sync:no-wait         # không chờ vector hoá — sẽ KHÔNG phát hiện được document hỏng
npm.cmd run sync -- --config path/brain.config   # cờ có giá trị: xem ghi chú dưới
```

> Trên **Windows PowerShell**, `npm` là `npm.ps1` và shim đó nuốt mất token `--`, nên
> `npm run sync -- --config …` không tới được script. Cờ nào cần giá trị thì gọi `npm.cmd`.
> Cờ không có giá trị đều đã có script npm riêng (`sync:rebuild`, `sync:no-verify`, …).
Máy không có Python → chạy trong container: `docker compose exec api python /work/brain/sync/sync.py`.

## Nhịp sync (tiêu chí C)

| Thời điểm | Sync? |
|---|---|
| Init lần đầu | Có (INITIALIZATION Bước 5) |
| **Mỗi turn ghi `decisions/` hoặc `mistakes/`** | **KHÔNG** — ghi file thôi |
| Cuối task, sau khi distill + prune | **Có** — một lần, gộp hết |
| Cuối phiên dài | Có |
| Mất `.sag-data` / đổi embedding model / state sai schema | `--rebuild` |

> **Ghi file là rẻ, sync là đắt.** Mỗi lần sync một file đã đổi = xoá document + ingest lại + SAG chạy LLM extract nền. Ghi từng turn nhưng sync gộp cuối task là nhịp đúng.

## Exit code — sync KHÔNG được im lặng khi tri thức không vào được não

`POST .../documents/ingest` chỉ **đăng ký** document; chunk hoá, vector hoá và trích xuất chạy
nền. Nếu chỉ nhìn lượt ingest thì embedding hỏng vẫn cho ra "done" và exit 0 — trong khi text nằm
trong DB **không có vector**, search không bao giờ trả nó về, và không ai biết. Đó là kiểu hỏng
tệ nhất: người dùng tin là mình đã ghi được.

Vì vậy sau khi ingest, sync **chờ** rồi mới kết luận:

| Kết quả | In ra | Exit |
|---|---|---|
| Mọi document `ready` | `done: every document is READY and searchable.` | `0` |
| Có document `failed` | lý do từng file + cách kiểm tra | **`1`** |
| Hết thời gian chờ mà còn đang xử lý | cảnh báo còn N document | `0` |

Thời gian chờ tối đa: `BRAIN_SYNC_WAIT` (giây, mặc định `900`). Bỏ hẳn bước chờ:
`npm run sync:no-wait` — khi đó sync không còn khả năng phát hiện document hỏng.

Hai nhóm nguyên nhân khi `failed`, phân biệt bằng chính dòng lỗi in ra:

| Lỗi nói về | Nghĩa là | Kiểm theo thứ tự |
|---|---|---|
| embedding / vector / index | chunk không có vector → search vector không thấy | `npm run embedding` → `npm run brain:logs` |
| extraction / LLM / provider | chưa cấu hình LLM hoặc provider lỗi → không có event/entity | Settings → Models |

> **Chưa cấu hình LLM thì mọi document sẽ `failed` và sync exit 1.** Đó là có chủ đích: một não
> chỉ có chunk mà không có event/entity là não chưa dùng được, và bản cũ im lặng về chuyện đó.

## Lưu ý
- Sau ingest, SAG chạy **extract nền** (LOADING → EXTRACTING → READY). Chỉ document **READY** mới search tốt.
- `document.title` = đường dẫn tương đối của file → dễ map ngược từ kết quả search về file thật.
