# brain / SYNC — Đồng bộ file → não (chống trùng)

SAG **không có dedup/idempotency**: nếu ingest mù một file đã sửa, nó tạo **document + chunk TRÙNG**. `sync.py` giải việc này bằng cách tự giữ map `file → document_id + sha256`.

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
python brain/sync/sync.py                 # đồng bộ incremental (chỉ file đổi)
python brain/sync/sync.py --rebuild       # xoá sạch source + ingest lại toàn bộ
python brain/sync/sync.py --no-verify     # bỏ gate — chỉ khi gỡ lỗi
python brain/sync/sync.py --config path/brain.config
```
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

## Lưu ý
- Sau ingest, SAG chạy **extract nền** (LOADING → EXTRACTING → READY). Chỉ document **READY** mới search tốt.
- `document.title` = đường dẫn tương đối của file → dễ map ngược từ kết quả search về file thật.
