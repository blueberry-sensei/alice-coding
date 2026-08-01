# TELEMETRY.md — Tiền và tri thức đi đâu

Brain tự ghi lại **mọi request LLM** (token vào/ra, chi phí, độ trễ, thành/bại), **mọi lần
agent lấy tri thức qua MCP** và **mọi diff được sync vào kho**. Xem tại
**Settings → Telemetry** trên UI của brain.

Mục đích: trả lời được ba câu mà trước đây chỉ đoán được —
*tinh luyện tài liệu tốn bao nhiêu tiền*, *lúc vibe agent đã lấy/ghi những tri thức gì*,
và *ai làm việc gì qua ALICE*.

Dữ liệu nằm trong chính DB của brain, **không gửi đi đâu**. Bản ghi cũ hơn `SAG_TELEMETRY_RETENTION_DAYS`
(mặc định 30 ngày) tự bị xoá. Tắt hẳn bằng `SAG_TELEMETRY_ENABLED=false`.

## 1. Request LLM — ghi tự động, không cần agent làm gì

| Stage | Là gì | Khi nào phát sinh |
|---|---|---|
| `extraction` | **Tinh luyện** — bóc thực thể/sự kiện từ tài liệu | `npm run sync`, hoặc upload tài liệu |
| `generation` | Sinh câu trả lời cho người dùng | Hỏi đáp trên UI |
| `embedding` | Tạo vector | Ingest và truy vấn |
| `probe` | Nút **Test** ở Settings → Model | Bấm tay |

Mỗi bản ghi có: model · provider · token vào/ra/tổng · chi phí · độ trễ · thành/bại + loại lỗi ·
và **tài liệu/job nào đã trả tiền cho nó** (bản ghi `extraction` mang `document_id`).

> **Chi phí trống nghĩa là "chưa biết giá", không phải "miễn phí".** Giá lấy từ bảng giá của
> LiteLLM; gateway tự host hoặc tên model lạ thì không có bảng giá → UI hiện dấu gạch và đếm
> riêng số lời gọi chưa biết giá. Đừng cộng chúng thành 0 đồng.

## 2. Tri thức agent lấy được — cũng tự động

Mỗi lần agent gọi tool MCP (`search`, `grep`, `get_entity`, `read`…) brain ghi lại: tool nào ·
câu hỏi · số bằng chứng trả về · `chunk_id` đã chạm · trích đoạn đầu kết quả · độ trễ · ai gọi.

Nhãn "ai gọi" do client khai — dùng để phân biệt, **không** dùng để phân quyền.
**Đây là việc của agent, không phải của người dùng**: INITIALIZATION lấy khối cấu hình bằng
`npm run mcp` rồi tự ghi vào config MCP của agent; người dùng chỉ restart agent.

- **stdio bridge:** biến môi trường nằm ngay trong lệnh bridge —
  `docker exec -i -e SAG_MCP_ACTOR=claude-code <brain>-api-1 python -m sag_api.mcp.server`.
- **HTTP `/mcp/`:** thêm `?actor=<tên>` hoặc header `x-alice-actor`.

Không khai thì bản ghi mang nhãn `mcp-stdio` / `mcp-http` — vẫn ghi, chỉ là không biết ai.

## 3. Việc giao cho sub-agent

Hai đường có bằng chứng khác nhau:

1. `list_sub_agents` tự ghi một event **Sub-agent registry**: agent đã đọc slot nào từ nguồn sự
   thật, không phải dò CLI hay đoán API.
2. `ask_sub_agent` tự ghi **delegation** + request LLM: provider/model, task, kết quả xem trước,
   token provider trả về, độ trễ và lỗi. Không gọi `log_agent_task` lần nữa.
3. `npm run sync` chỉ ghi **Knowledge write** sau khi diff đã ingest và `.sync-state.json` đã lưu:
   danh sách file tạo/cập nhật/xoá, source và tổng `+ / ~ / -`. Sync không đổi file nào thì không
   tạo event nhiễu. Nếu ingest đã xong nhưng ghi telemetry lỗi, terminal phải in `WARNING`; không
   được nói telemetry đã ghi thành công.

Sub-agent chạy bằng CLI trên máy (opencode, codex, gemini…) **không đi qua Brain**, nên vẫn phải
được orchestrator khai bằng:

```
log_agent_task(agent="opencode-go", task="đổi 12 form sang schema mới",
               status="done", model="grok-code", note="npm run typecheck xanh")
```

`status`: `started` khi giao, rồi ghi lại `done`/`failed` khi xong. Có `input_tokens` /
`output_tokens` / `cost_usd` do CLI báo thì điền — bản ghi đánh dấu **`reported`** để phân biệt
với số brain tự đo được. Không có thì bỏ trống, **đừng ước lượng**.

Ai không cắm MCP thì dùng đường HTTP tương đương: `POST /api/v1/telemetry/agent-events`.

## 4. Đọc trang Telemetry thế nào

Hai danh sách mở với 50 bản ghi mới nhất; **Tải thêm** dùng pagination để đọc lịch sử cũ mà không
đẩy một payload lớn vào browser ngay từ đầu. **Xuất báo cáo** tải toàn bộ request LLM và hoạt động
agent trong khoảng 1/7/30 ngày đang chọn thành JSON, kèm summary và thời điểm export.

| Thấy gì | Nghĩa là |
|---|---|
| `extraction` chiếm gần hết chi phí | Bình thường — tinh luyện là phần đắt nhất. So với số tài liệu đã ingest để biết đắt bất thường không. |
| Nhiều `probe` | Đang bấm Test nhiều; mỗi lần bấm là một lần tốn tiền thật. |
| `generation` tăng mà `knowledge call` không tăng | Agent đang trả lời bằng trí nhớ context, không tra não. |
| Nhiều `search` nhưng `result 0` | Câu truy vấn lệch với tri thức đã ingest, hoặc chưa sync. |
| Có `Sub-agent registry` nhưng không có `delegation` | Agent đã đọc cấu hình nhưng chưa gọi `ask_sub_agent` hay chưa khai lượt CLI. |
| `delegation` có kết quả xem trước | Lượt này đi qua `ask_sub_agent`; Brain đo được request thật. |
| `delegation` chỉ có note verify | Lượt CLI ngoài Brain do orchestrator tự khai bằng `log_agent_task`. |
| Agent nói đã dùng CLI nhưng không có `delegation` | Agent đã vi phạm protocol và không gọi `log_agent_task`; Brain không thể tự quan sát process tuỳ ý trên host. |
| `Knowledge write` | Diff file đã thực sự được `sync` đưa vào Brain; badge không xuất hiện chỉ vì agent sửa Markdown trên host. |
| Lời gọi thất bại dồn vào một model | Xem thêm Settings → Model → Call history để biết loại lỗi và nhà nào bị tắt. |

## 5. Ranh giới — nói thẳng để không tin nhầm

- Brain chỉ thấy lời gọi **đi qua chính nó**. Token mà Claude Code / Codex tiêu cho phiên vibe
  nằm ở nhà cung cấp của agent đó, **không** có ở đây.
- Token của `ask_sub_agent` lấy từ response provider; số của `log_agent_task` vẫn là **do khai**.
- `ask_sub_agent` không có filesystem. Kết quả telemetry chứng minh model đã trả lời, không chứng
  minh code đã được sửa hay verify.
- Chi phí là **ước tính theo bảng giá**, không phải hoá đơn. Hoá đơn thật vẫn ở phía nhà cung cấp.
