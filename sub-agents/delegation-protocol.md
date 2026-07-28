# Delegation Protocol (agent-agnostic)

Quy trình chung khi Alice giao việc cho sub-agent. Có hai đường: `brain` để lấy phân tích/review
không đụng filesystem; `host-cli` để coding agent tự đọc/sửa/verify file.

## Vòng lặp chuẩn

```
0. Alice: kiểm ngưỡng delegate (README.md) — không đủ ≥3 dấu hiệu thì TỰ LÀM
1. Alice: recall qua brain → khảo sát repo tối thiểu để viết spec đúng pattern
2. Alice: gọi `list_sub_agents`, chọn execution mode theo task
3a. `brain`: `ask_sub_agent(task, context=code + diff + tri thức)` → Alice kiểm chứng và tự áp dụng
3b. `host-cli`: task spec + base prompt → sub-agent tự sửa file, tự verify
4. Alice: review source/diff + chạy verify project
5. Alice: thu hồi bài học vào mistakes/decisions/wiki
6. Alice: đạt → báo cáo; chưa → viết spec sửa lỗi, quay lại bước 3
```

## Bước 1–2: Alice viết spec

Spec tốt = sub-agent không phải đoán. Bắt buộc có: **Mục tiêu**; **Context repo** (branch, file liên quan, pattern phải theo — chỉ đích danh file mẫu); **Thay đổi chính xác**; **Ràng buộc** (copy từ ALICE.md/convention project); **Definition of done** + cách tự verify; **KHÔNG được đụng** vào đâu; **Output**: tóm tắt file đã đổi.

Khảo sát repo *đủ để viết spec đúng* — đừng đọc thừa (đó là token cần tiết kiệm). Không chắc pattern thì đọc đúng 1 file mẫu rồi trích dẫn trong spec.

## Bước 3a: gọi qua Brain

- Gọi `list_sub_agents`, không dò CLI để đoán registry.
- `ask_sub_agent` chỉ nhận `provider`, `task`, `context`; không nhận credential hoặc base URL.
- `context` phải chứa đoạn code/diff, ràng buộc và tri thức đã recall đủ để trả lời.
- Kết quả là **tư vấn**, không phải bằng chứng file đã sửa hay test đã chạy.
- Tool tự ghi telemetry; không gọi `log_agent_task` lặp lại.

## Bước 3b: chạy host CLI (kỷ luật token)

**Luôn gọi qua [base-prompt.md](base-prompt.md)** — prepend preamble chuẩn (ép sub-agent đọc ALICE + mistakes + đúng trang wiki) rồi mới tới `## NHIỆM VỤ`. Không tự chế base prompt riêng.

- Ưu tiên **non-interactive + auto-approve permission** (không kẹt chờ xác nhận).
- **Redirect log ra file** thay vì đọc thẳng: `... > run.log 2>&1`. Alice chỉ đọc `tail` khi cần debug.
- Yêu cầu sub-agent ghi **1 file SUMMARY ngắn** thay vì đọc toàn transcript.
- **Chạy nền** nếu model chậm (model free thường >2 phút cho task nhỏ) để không bị timeout cắt ngang.
- Scope hẹp: mỗi lần 1 task rõ ràng.

## Bước 4: Review gate (Alice BẮT BUỘC làm)

Không tin sub-agent mù quáng. Mỗi lần xong:
1. `git diff` + `git status` (bắt file lạ/mới ngoài dự kiến).
2. Chạy **verify của project** (build/typecheck/lint/test theo `ALICE.md`).
3. Kiểm ràng buộc: theo pattern? đụng file cấm? thêm dependency lạ?
4. Đọc kỹ logic chỗ rủi ro cao (auth, payment, data mutation) — nơi Alice thêm giá trị.

Chưa đạt → **không tự sửa tay** (tốn token Alice). Viết spec-fix ngắn, giao lại.

## Bước 5: Thu hồi tri thức (BẮT BUỘC — chống rò rỉ bài học)

> Vấn đề của bản trước: protocol cấm Alice đọc transcript sub-agent (đúng, để tiết kiệm token) — **nhưng bài học sub-agent vấp phải nằm chính trong transcript đó**. Alice chỉ thấy `git diff` nên không distill được. Kết quả: **mỗi lần delegate là một lần tri thức bị mất trắng**, mâu thuẫn trực tiếp với tiêu chí C.

Cách bịt: bắt sub-agent **tự viết bài học ra file**, Alice đọc file đó thay vì transcript.

1. Base prompt đã bắt sub-agent ghi mục **`## BÀI HỌC`** trong `SUBAGENT_SUMMARY.md` (giả định sai, chỗ tài liệu/wiki nói sai so với code, gotcha, cách chẩn đoán).
2. Alice **đọc mục đó** (ngắn, rẻ — không phải transcript).
3. Distill:
   - Giả định sai / bug / cách chẩn đoán tái dùng → entry `M-XXXX` trong [`mistakes/LOG.md`](../mistakes/README.md), ghi rõ *"phát hiện khi delegate"*.
   - Wiki nói sai so với code → **sửa trang wiki ngay**, không chỉ ghi nhận.
   - Pattern/ràng buộc mới của project → `wiki/` hoặc `D-XXXX` nếu là ý chí Bệ hạ.
4. `SUBAGENT_SUMMARY.md` là **file tạm** — distill xong thì xoá, đừng để nó thành trụ cột thứ 7 không ai đọc.

Bỏ bước này = task chưa hoàn thành, ngang với quên verify.

## Bước 5b: Ghi telemetry cho host CLI

Chỉ sau lượt `host-cli`, gọi tool MCP của brain:

```
log_agent_task(agent="<slot>", task="<một dòng>", status="done|failed",
               model="<model đã chạy>", note="<lệnh verify + kết quả thật>")
```

Giao việc dài thì ghi `status="started"` lúc giao và ghi lại lúc xong. CLI có báo token/chi phí
thì điền `input_tokens` / `output_tokens` / `cost_usd`; **không có thì để trống, đừng ước lượng** —
bản ghi được đánh dấu `reported` chính vì nó là số do agent khai.

Không dùng bước này cho `ask_sub_agent`: Brain đã tự ghi request, token, kết quả xem trước và trạng
thái thật. Với host CLI, khai là bắt buộc vì nó **không đi qua Brain**, nên đây là đường duy nhất để
"ai đã làm gì qua ALICE" hiện ra ở Settings → Telemetry cạnh chi phí tinh luyện và dấu vết truy
xuất tri thức. Xem [`../brain/TELEMETRY.md`](../brain/TELEMETRY.md).

## Red flags khi review diff sub-agent

- Đổi config bị cấm; thêm pattern mới thay vì theo pattern sẵn có; xoá/sửa file ngoài scope; "sửa" test cho pass thay vì sửa code; bịa API/endpoint; hardcode secret/giá trị; nuốt lỗi trả success.
- **Mục `BÀI HỌC` bỏ trống hoặc sáo rỗng** ("mọi thứ suôn sẻ") trong khi diff cho thấy nhiều lần thử sai → sub-agent đang giấu; hỏi lại hoặc tự đọc `tail` log.

## An toàn

Branch riêng + commit mốc trước khi giao. Cân nhắc git worktree để cô lập. Không giao thao tác khó đảo ngược cho sub-agent tự động.
