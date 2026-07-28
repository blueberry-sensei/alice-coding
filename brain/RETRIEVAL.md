# brain / RETRIEVAL — Giao thức query não (để "không sót")

Tiêu chí **A — tự nạp ký ức**. Áp dụng **đầu mỗi task** (và lặp lại sau auto-compact — tiêu chí B).

## 8 tool MCP (read-only)
`list_sources` · `list_documents` · `outline` · `search` · `grep` · `get_chunk` · `read` · `get_entity`

## Funnel bắt buộc
1. **`list_sources`** — xác nhận scope + lấy `source_id` (`<BRAIN_ID>-knowledge`).
2. **Truy vấn đa góc** (không chỉ 1 lần) — recall theo nhiều mặt của task:
   - theo **mô tả task** (câu hỏi/khái niệm) → `search`.
   - theo **tên file/module/định danh** chính xác → `grep`.
   - theo **triệu chứng lỗi / từ khoá** nếu là bug.
3. **`get_entity` — BƯỚC QUYẾT ĐỊNH "không sót":** từ kết quả trên, rút các **entity chính** (tên module, khái niệm, dịch vụ, lỗi) → gọi `get_entity(name)` cho từng cái để kéo tri thức **liên quan gián tiếp** qua entity chung. MCP `search` mặc định chỉ semantic; multi-hop lộ ra chủ yếu ở đây.
4. **`get_chunk` / `read`** — chỉ lấy đúng đoạn cần (đừng `read` cả file lớn).

> Task high-risk (auth/payment/data/sync — xem `ALICE.project.md` mục 4): thêm một vòng recall bằng REST `POST /search` `strategy="multi"` (LLM rerank quan hệ).

## Tiêu chí DỪNG (bao nhiêu là đủ?)

"Query đa góc" mà không có điểm dừng thì hoặc query một lần rồi tự cho là đủ, hoặc query mãi. Được coi là **đủ** khi thoả **cả ba**:

1. **Bão hoà:** một vòng `search`/`grep`/`get_entity` mới **không ra thêm document nào chưa thấy**.
2. **Phủ hết vùng:** mọi module mà task sẽ **sửa file** đều đã có ít nhất một hit (wiki hoặc changelog). Không có hit → **không phải là "không có tri thức"**, mà là dấu hiệu module đó chưa có trang wiki → nói thẳng với Bệ hạ, đừng lặng lẽ bỏ qua.
3. **Đã bung quan hệ:** đã gọi `get_entity` cho **mọi** entity chính rút ra ở bước 2, không chỉ cái đầu tiên.

Chưa thoả cả ba mà đã bắt tay làm = vi phạm tiêu chí A.

## Lọc theo trạng thái — BẮT BUỘC

Não trả về **mọi** entry, kể cả entry đã chết. Trước khi dùng làm căn cứ:

| Trạng thái | Được dùng làm căn cứ? |
|---|---|
| `ACTIVE` | Có |
| `RESOLVED` (mistakes) | **Không** — đã fix tận gốc, dùng nó sẽ dẫn tới phòng thủ thừa |
| `SUPERSEDED → X` | **Không** — phải đi theo `X` và dùng entry đó |
| `RETIRED` (decisions) | **Không** |

Hai entry `ACTIVE` mâu thuẫn nhau → **cái có ngày mới hơn thắng**, và đó là lỗi dữ liệu: ghi ngay `SUPERSEDED` cho cái cũ trong chính task này (xem [`KNOWLEDGE.md`](KNOWLEDGE.md)). Xung đột giữa các trụ cột: `decisions/` thắng `wiki/` về *nên làm thế nào*; **source code thật** thắng tất cả về *hệ thống đang ra sao*.

## Kỷ luật citation (bắt buộc)
- Mỗi tri thức dùng để quyết định phải gắn `chunk_id`/`document_id`.
- **Luôn map ngược ra `path:line#anchor` thật và MỞ file đó ra xem** trước khi tin — não chỉ là index, file mới là chân lý. Trang wiki có thể đã cũ hơn code; `npm run verify` bắt được citation trỏ sai, nhưng **không** bắt được nội dung mô tả đã lỗi thời.

## Proof-of-load (forcing function cho tiêu chí A)

Đầu task, **in ra checklist** chứng minh đã nạp ký ức. Checklist phải nêu **con số tool call thật** — đây là điểm khác bản trước: một checklist chung chung thì model nào cũng "in đẹp" được mà không thực sự query.

```
Ký ức đã nạp (brain: ONLINE)
- tool call: search×3 · grep×2 · get_entity×4 · read×2
- wiki: payments.md [doc=…] — luồng refund
- mistakes: M-0012 double-charge khi retry [doc=…] (ACTIVE)
- decisions: D-0003 không tự thêm dependency (ACTIVE)
- entity "wholesale_amount" → 3 event liên quan
- bỏ qua: M-0004 (RESOLVED), D-0001 (SUPERSEDED → D-0003)
- tiêu chí dừng: bão hoà ✓ · phủ module payments+billing ✓ · get_entity hết entity chính ✓
- vùng chưa có tri thức: module `notifications` KHÔNG có trang wiki → sẽ đọc source trực tiếp
```

Bỏ bước này = task **chưa** đạt kỷ luật (soi ở verify — `ALICE.md` mục 4).

## Fallback khi brain offline / chưa bật
1. Probe `GET /system/ready`. Không 200 → coi như brain OFF.
2. Chuyển sang **đọc file**: [`mistakes/LOG.md`](../mistakes/README.md) (phân tầng theo tag) + [`decisions/LOG.md`](../decisions/README.md) (toàn bộ `ACTIVE`) + [Wiki Router](../wiki/ROUTER.md) → trang khớp + context digest gần nhất.
3. **Cảnh báo Bệ hạ**: *"Não offline — recall theo chế độ file, có thể sót tri thức liên quan gián tiếp."*
4. Không bao giờ hard-fail vì thiếu brain.

> Sub-agent **luôn** không được mount MCP brain. Với `ask_sub_agent`, orchestrator truyền tri thức
> đã recall cùng code/diff cần xem trong `context`; với host CLI, nhét chúng vào task spec. Xem
> [`sub-agents/delegation-protocol.md`](../sub-agents/delegation-protocol.md).
