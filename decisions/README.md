# decisions — Quyết định & sở thích của Bệ hạ (ghi theo TURN)

Trụ cột này giữ thứ mà 4 trụ cột kia **không có chỗ chứa**: điều Bệ hạ *nói ra* chứ không phải điều code *thể hiện*.

- `wiki/` = hệ thống **đang** thế nào.
- `changelog/` = code **đã đổi** gì.
- `mistakes/` = Alice **đã sai** gì.
- `context/` = **mạch truyện** của một phiên.
- **`decisions/` = luật bất thành văn của Bệ hạ** — sở thích, quy ước, hướng đã bị loại, business rule chỉ tồn tại trong đầu Bệ hạ.

> Vì sao tách riêng: một câu như *"đừng tạo abstraction sớm"* hay *"chỗ này ưu tiên đơn giản hơn đúng tuyệt đối"* **không phải incident** (không có root cause để ghi vào `mistakes/`), **không phải thay đổi code** (không có changelog), và nếu chỉ nằm trong một digest `context/` thì nó chết chìm cùng phiên đó. Nó cần một nơi **tra được, ưu tiên cao, không bao giờ hết hạn theo phiên**.

## Luật ghi — theo TURN, không đợi cuối task

Đây là khác biệt then chốt so với 4 trụ cột kia. **Không đợi task xong. Không đợi phiên kết thúc.** Ghi **ngay trong turn** phát sinh, vì phiên có thể chết hoặc bị auto-compact bất cứ lúc nào.

**Trigger bắt buộc — thấy một trong các dấu hiệu sau là ghi ngay:**

| Bệ hạ nói kiểu | Ví dụ | Loại |
|---|---|---|
| Bác / sửa hướng Alice đang làm | *"không, đừng làm thế"*, *"sai rồi"*, *"tôi không muốn kiểu đó"* | `hướng-đã-loại` |
| Nêu sở thích, khẩu vị kỹ thuật | *"tôi thích code phẳng"*, *"đừng thêm thư viện"* | `sở-thích` |
| Chốt một hướng sau khi cân nhắc | *"thôi dùng cách B"* | `quyết-định` |
| Giải thích luật nghiệp vụ không có trong code | *"khách VIP thì không tính phí này"* | `nghiệp-vụ` |
| Đặt ranh giới / vùng cấm | *"đừng bao giờ đụng bảng đó"* | `ranh-giới` |

Không có trigger nào khớp → **không ghi**. Trụ cột này quý vì nhỏ và đúng; nhồi cho đầy là phá nó.

**Chi phí:** ghi file là rẻ → làm ngay. `sync` vào não là đắt → **gộp lại**, chạy một lần ở cuối task (xem [`brain/SYNC.md`](../brain/SYNC.md) mục *Nhịp sync*). Đừng sync sau mỗi turn.

## Format

Mỗi entry một khối theo [`_TEMPLATE.md`](_TEMPLATE.md), **mới nhất trên cùng**, bắt buộc có:

- **ID ổn định `D-XXXX`** — không bao giờ đổi, không tái sử dụng. Để `changelog/`, `wiki/`, `mistakes/` link tới được.
- **Trạng thái** — `ACTIVE` · `SUPERSEDED → D-XXXX` · `RETIRED`.
- **Nguồn** — trích nguyên văn ngắn lời Bệ hạ + ngày. Đây là bằng chứng; không có nguồn thì đó là Alice tự bịa luật cho mình.

## Khi Bệ hạ đổi ý

**Tuyệt đối không xoá entry cũ, cũng không thêm entry mới mâu thuẫn rồi để đó.** Đúng quy trình:

1. Thêm entry mới `D-0009` ghi luật mới.
2. Sửa entry cũ `D-0004`: `Trạng thái: SUPERSEDED → D-0009`.

Nhờ vậy lịch sử vì-sao vẫn còn, mà retrieval không bị nhiễu — [`brain/RETRIEVAL.md`](../brain/RETRIEVAL.md) bắt buộc **bỏ qua entry SUPERSEDED/RETIRED khi lấy làm căn cứ quyết định**. `npm run verify` sẽ báo lỗi nếu ID đích không tồn tại.

## Ưu tiên khi xung đột

`decisions/` **thắng** `wiki/` và tài liệu cũ khi nói về *nên làm thế nào* (vì đó là ý chí Bệ hạ, còn wiki chỉ mô tả hiện trạng). Nhưng vẫn **thua** [`ALICE.md`](../ALICE.md) và thua **source code thật** khi nói về *hệ thống đang ra sao*. Xem [`ALICE.md`](../ALICE.md) mục 1.
