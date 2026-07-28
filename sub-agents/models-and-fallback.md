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
sách model live. Chỉ `Custom provider` mới cho nhập model thủ công. `model_verified=true` chứng minh
key đã qua discovery và model có trong response tại lúc lưu, nhưng chưa chứng minh CLI trên máy hiện
tại chạy được; INITIALIZATION vẫn phải dò CLI/auth và chạy một smoke task trước khi ghi
provider/model vào `ALICE.project.md`.

Credential lưu trong brain được mã hoá và API chỉ trả trạng thái `credential_set`; danh sách model
được gọi live, không được nướng vào template. Không chép credential vào `ALICE.project.md`, task
spec, log hay report. Registry cũng **không tự đăng nhập CLI**: CLI phải được xác nhận bằng chính cơ
chế đăng nhập và smoke của nó.

## Quy tắc chọn và fallback

1. Chỉ giao việc cho slot đang **bật** trong Settings và đã smoke trên máy hiện tại.
2. Dùng policy đã bake ở `ALICE.project.md` mục 7; không tự suy ra ưu tiên từ thứ tự card trên UI.
3. **Lỗi thông thường** (network, timeout, 5xx, connection reset) → retry cùng model 2–3 lần với
   backoff ngắn.
4. **Hết quota / rate limit** (429, "quota exceeded", "resource exhausted", "rate limit") → chuyển
   sang slot dự bị kế tiếp trong policy của project. Không quay lại slot vừa hết quota trong cùng task.
5. **Lỗi auth** (401/403, "invalid api key", "unauthenticated") → dừng slot đó và báo Bệ hạ cần
   đăng nhập lại. Không tự đổi credential.
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
