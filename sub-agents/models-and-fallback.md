# Model policy & Fallback

Quy định cách chọn model và tụt ưu tiên khi sub-agent lỗi/hết quota.

## Nguồn sự thật

Provider/model được bật cho project nằm ở **Brain → Settings → Sub Agents**, không nằm trong file
template này và không lấy từ MCP. Brain có sẵn sáu slot:

1. Claude
2. Codex
3. OpenCode GO
4. OpenCode ZEN
5. Gemini CLI
6. Custom provider

Năm slot đầu **không có bảng model hard-code**: Brain xác thực API key với provider rồi lấy danh
sách model live. Chỉ `Custom provider` mới cho nhập model thủ công. Agent đọc registry bằng
`list_sub_agents`, không đoán REST endpoint và không suy từ CLI trên máy.

Credential lưu trong brain được mã hoá và API chỉ trả trạng thái `credential_set`; danh sách model
được gọi live, không được nướng vào template. `ask_sub_agent` giải mã key **bên trong Brain** và chỉ
gửi tới endpoint đã lưu/cố định của slot; key không được trả ra MCP. Không chép credential vào
`ALICE.project.md`, task spec, log, report hay biến môi trường host.

## Registry được dùng lúc VIBE như thế nào

Có hai execution mode, không được trộn:

### `brain` — model tư vấn qua MCP

1. Gọi `list_sub_agents`; chỉ chọn slot `callable=yes` và phù hợp policy ở
   [`../ALICE.project.md`](../ALICE.project.md) mục 7.
2. Main agent đã đọc source/recall tri thức, rồi truyền **task + code/diff + ràng buộc** vào
   `ask_sub_agent`.
3. Brain gọi provider bằng credential đã lưu, trả text và tự ghi telemetry. Không gọi
   `log_agent_task` lần nữa.
4. Main agent kiểm chứng kết quả với source thật trước khi áp dụng.

Mode này hợp phân tích, review diff, tìm edge case, đề xuất test. Nó **không có filesystem, shell,
MCP brain hay quyền sửa code**. Nếu main agent không truyền context thì sub-agent không biết project.

### `host-cli` — coding agent có filesystem

1. CLI phải được cài, đăng nhập bằng auth riêng và smoke thật.
2. Gọi qua [base-prompt chuẩn](base-prompt.md), để CLI đọc/sửa/verify trên filesystem.
3. Main agent review diff + bài học.
4. Vì Brain không thấy CLI, khai `log_agent_task` sau mỗi trạng thái.

Credential trong registry **không rót vào CLI**. Không bảo Bệ hạ dán lại key chỉ để dùng mode
`brain`; chỉ xin auth host khi Bệ hạ thật sự chọn mode `host-cli`.

## Quy tắc chọn và fallback

1. Mode `brain`: chỉ gọi slot `callable=yes` từ `list_sub_agents`; mode `host-cli`: chỉ gọi CLI đã
   smoke trên máy hiện tại.
2. Dùng policy ở `ALICE.project.md` mục 7; không tự suy ra ưu tiên từ thứ tự card trên UI.
3. **Lỗi thông thường** (network, timeout, 5xx, connection reset) → retry cùng model 2–3 lần với
   backoff ngắn.
4. **Hết quota / rate limit** (429, "quota exceeded", "resource exhausted", "rate limit") → chuyển
   sang slot dự bị kế tiếp trong policy của project. Không quay lại slot vừa hết quota trong cùng task.
5. **Lỗi auth** (401/403, "invalid api key", "unauthenticated") → dừng slot đó. Mode `brain` yêu
   cầu cập nhật credential trong Settings; mode `host-cli` yêu cầu đăng nhập lại CLI. Không tự đổi key.
6. **Model không tồn tại / bị gỡ** → dừng slot, tải lại danh sách live trong Settings, đối chiếu CLI
   rồi smoke lại. Không gõ model khác vào preset để lách validation; nếu provider không có contract
   discovery mặc định thì dùng `Custom provider`.

## Ghi nhận khi phải fallback

- Nếu một task phải đổi từ hai slot trở lên, hoặc slot mặc định liên tục hết quota → ghi một dòng vào
  [`changelog`](../changelog/README.md) của module liên quan (hoặc `mistakes/` nếu là vấn đề lặp lại).
- Report cho Bệ hạ phải nói rõ provider/model cuối cùng đã làm, vì chất lượng khác nhau theo model.

## Nhắc về chất lượng

Model rẻ/nhanh hợp task cơ học; model mạnh hợp review kiến trúc, security và debug nhiều tầng.
Spec càng rõ, task càng nhỏ và review gate của Alice càng chặt thì fallback càng an toàn.
