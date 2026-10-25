# brain / SYNC — Đồng bộ file → não theo từng entry, không cần LLM

File trong `knowledge/` là source-of-truth; não là index dẫn xuất. `sync.py` đẩy tri thức vào não
theo **entry**, kèm **sự kiện đã bóc sẵn** — brain chỉ chia chunk và gọi model embedding, **không
gọi LLM nào**. Vì vậy sync không còn phụ thuộc quota của nhà cung cấp LLM, không còn lỗi schema của
model, và sửa một entry chỉ tốn đúng một entry.

Sau một lượt có thay đổi, sync tự ghi event **Knowledge write** vào Settings → Telemetry với source,
danh sách entry tạo/cập nhật/xoá và tổng `+ / ~ / -`. Lượt không có diff không tạo event.

## Entry — đơn vị đồng bộ

| File | Một entry là |
|---|---|
| `decisions/LOG.md`, `mistakes/LOG.md` | một khối `## D-xxxx …` / `## M-xxxx …` |
| mọi file khác trong phạm vi | một mục `## …`; phần trước `##` đầu tiên (H1 + mở bài) là một entry riêng |

Mỗi entry là một document trong não, tên `<file>#<ID hoặc tiêu đề mục>` (ví dụ
`decisions/LOG.md#D-0042`). `## ` nằm trong code fence không tách entry.

## Sự kiện — agent tự bóc, brain không bóc

Mỗi entry mang theo danh sách **sự kiện**: mệnh đề trọn nghĩa (đọc riêng vẫn hiểu), dòng nguồn của
nó (để cite đúng dòng) và các entity của nó. Có hai cách có sự kiện:

**1. Agent tự viết (bắt buộc cho entry mới)** — thêm khối `- **Sự kiện:**` vào entry, mỗi dòng con một
mệnh đề. Entry LOG ghi từ `EVENTS_REQUIRED_FROM` (mặc định 2026-10-25, `tools/verify.config`) mà thiếu khối
này thì `npm run verify` cảnh báo `C10`:

```md
## D-0042 · [2026-10-22] Hoàn tiền chỉ đi qua một cổng, có idempotency key · #payments

- **Trạng thái:** ACTIVE
- **Luật:** …
- **Sự kiện:**
  - Mọi lệnh hoàn tiền đi qua `refundOrder()` ở `src/payments/refund.ts`, thay luật cũ D-0017.
  - `refundOrder()` bắt buộc nhận `idempotency_key`; gọi lại cùng key trả kết quả lần đầu, không hoàn lần hai.
  - Webhook của cổng thanh toán không được tự hoàn tiền; nó chỉ ghi trạng thái vào `payment_events`.
```

- Entity của một dòng: mọi đoạn trong `backtick` (đường dẫn `a/b.ts:12#x` được rút về `a/b.ts`),
  mọi ID `D-xxxx`/`M-xxxx`, mọi `#tag`; cộng ID + tag của entry (LOG) hoặc đường dẫn file (file khác).
- Có khối này thì brain dùng **đúng các dòng đó** (cộng một sự kiện tiêu đề mang ID + trạng thái).

**2. Entry cũ không có khối** — sync suy sự kiện **tất định** từ cấu trúc sẵn có của entry: mỗi bullet
(`**Luật:**`, `**Vì sao:**`, từng mục đánh số…), mỗi đoạn văn, mỗi dòng bảng, mỗi tiêu đề con là một
sự kiện; bullet con mang theo field và bullet cha làm ngữ cảnh (`D-0042 (ACTIVE) › Luật › … › webhook
chỉ ghi trạng thái`). Entity lấy y như cách 1. Không có LLM nào trong đường này.

Đổi cách tách entry/suy sự kiện thì bump `DERIVE_VERSION` trong `sync.py`: mọi entry được gửi lại
đúng một lần.

## Gate: verify chạy TRƯỚC, chỉ giữ lại đúng chỗ hỏng

`sync.py` chạy [`tools/verify.py`](../tools/verify.py) `--json` trước mọi thứ:

| ERROR của verify gắn với | Sync làm gì |
|---|---|
| một dòng nằm trong entry X | **giữ lại** X — não giữ bản trước đó của X; mọi entry khác vẫn sync |
| một file trong phạm vi nhưng không có dòng (vd `ROUTER.md` thiếu trang) | giữ lại mọi entry của file đó, kể cả không xoá entry đã biến mất |
| một file ngoài phạm vi não (vd `ALICE.project.md`) | không giữ gì, chỉ in ra |
| không gắn được với file nào | **dừng cả lượt** — không biết phần nào sạch |

Mỗi entry bị giữ được in kèm lý do (`= HELD decisions/LOG.md#D-0123 …`) và đếm trong dòng `done:`.
Luật verify **không** bị nới: `npm run verify` vẫn đỏ cho tới khi sửa xong, chỉ là một citation mồ
côi ở chỗ này không còn chặn tri thức ở chỗ khác.

`--no-verify` tồn tại để gỡ lỗi. Dùng nó để né gate là vi phạm `ALICE.md` mục 6.

## Cách hoạt động

- **State** `brain/.sync-state.json` (gitignore):
  `{ "schema": 3, "source_id": …, "entries": { "decisions/LOG.md#D-0042": {"document_id": …, "sha256": …, "line": 3} }, "retire": [] }`.
- `sha256` băm **nội dung** entry (không băm số dòng). Với từng entry:
  - **Mới** → `POST /sources/{id}/documents/ingest-extracted` (text + dòng bắt đầu + sự kiện).
  - **Đổi** → ingest bản mới; document cũ vào `retire`.
  - **Chỉ dời dòng** (sửa entry phía trên) → `POST /sources/{id}/documents/origins`, không nhúng lại gì.
  - **Trùng hash, đúng dòng** → bỏ qua.
  - **Mất khỏi file** → document vào `retire`.
- Chờ mọi document đang theo dõi `ready` → chờ source idle → xoá đúng các document trong `retire`.
  Có document `failed` hoặc còn đang xử lý thì **không xoá gì**: bản cũ vẫn là thứ search thấy.

### Schema của state
State v2 (theo file) được chuyển tự động: document theo file không bị xoá trước mà nằm trong
`retire`, vẫn trả lời search cho tới khi mọi entry mới `ready` — não không có lúc rỗng. Schema lạ
khác → `sync.py` dừng và yêu cầu `npm run sync:rebuild`.

### Citation
Brain lưu `origin_path` + `origin_line` của mỗi entry và dòng bắt đầu của từng chunk/sự kiện. MCP
`search`, `grep`, `get_chunk`, `outline`, `get_entity` in `Cite: decisions/LOG.md:1234 · id=…`; `read`
đánh số theo dòng của chính file đó. Vẫn **mở file ra xem** trước khi tin (xem `RETRIEVAL.md`).

## Phạm vi (mặc định)
- **Include:** `wiki/`, `mistakes/`, `decisions/`, `context/`, `changelog/` (chỉnh qua `BRAIN_INCLUDE`).
- **Exclude:** file chứa `_TEMPLATE.md` (chỉnh qua `BRAIN_EXCLUDE`).
- **KHÔNG** đụng source code, cũng **không** đụng file luật/hướng dẫn thuần template (`ALICE.md`, `ALICE.project.md`, `INITIALIZATION.md`, `README`, `UPGRADE`, `MIGRATIONS`, `prompts`).

## Chạy
```bash
npm run sync                 # đồng bộ incremental (chỉ entry đổi)
npm run sync:rebuild         # gửi lại mọi entry, rồi mới xoá mọi document cũ của source
npm run sync:no-verify       # bỏ gate — chỉ khi gỡ lỗi
npm run sync:no-wait         # không chờ vector hoá — KHÔNG phát hiện document hỏng, không xoá bản cũ
npm.cmd run sync -- --config path/brain.config   # cờ có giá trị: xem ghi chú dưới
```

> Trên **Windows PowerShell**, `npm` là `npm.ps1` và shim đó nuốt mất token `--`, nên
> `npm run sync -- --config …` không tới được script. Cờ nào cần giá trị thì gọi `npm.cmd`.
> Cờ không có giá trị đều đã có script npm riêng (`sync:rebuild`, `sync:no-verify`, …).

Brain phải chạy image có `ingest-extracted` (alice-brain mới). Image cũ trả 404/405 và sync dừng với
hướng dẫn `npm run brain` — **không** lùi về đường LLM.

## Nhịp sync (tiêu chí C)

| Thời điểm | Sync? |
|---|---|
| Init lần đầu | Có (INITIALIZATION Bước 5) |
| **Mỗi turn ghi `decisions/` hoặc `mistakes/`** | Ghi file; sync khi xong task |
| Cuối task, sau khi distill + prune | **Có** — một lần, gộp hết |
| Mất dữ liệu não / đổi embedding model / state sai schema | `npm run sync:rebuild` |

> Sync một entry đã đổi = nhúng lại vài chục câu bằng model embedding cục bộ, không còn LLM. Vẫn
> gộp cuối task cho gọn, nhưng sync không còn là việc đắt. Lần đầu (hoặc rebuild) phải nhúng cả kho.

## Exit code — sync KHÔNG được im lặng khi tri thức không vào được não

`ingest-extracted` chỉ **đăng ký** document; chunk + vector hoá chạy nền. Vì vậy sau khi gửi, sync
**chờ** rồi mới kết luận:

| Kết quả | In ra | Exit |
|---|---|---|
| Mọi document `ready`, bản cũ đã xoá | `done: +a ~b -c moved d (…, held back h, …)` | `0` |
| Có entry bị giữ vì verify | dòng `= HELD …` cho từng entry + `held back h` trong `done:` | `0` |
| Có document `failed` hoặc hết `BRAIN_SYNC_WAIT` mà còn đang xử lý | lý do từng document; bản cũ được giữ | **`1`** |

Thời gian chờ tối đa: `BRAIN_SYNC_WAIT` (giây, mặc định `3600`, đủ cho lượt full đầu tiên). Document `failed` gần như luôn là lỗi
embedding: `npm run embedding` → `npm run brain:logs`.

## Lưu ý
- Upload tài liệu thủ công qua web vẫn đi đường LLM cũ (cần Settings → Models). Sync tri thức
  không bao giờ đi qua đường đó.
- `document.filename` = `<file>#<entry>` → map ngược từ kết quả search về file thật rất dễ; `Cite:`
  còn cho đúng dòng.
