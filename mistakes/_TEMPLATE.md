# Mistake entry template

Copy khối dưới, dán lên **đầu** `LOG.md`. ID lấy số kế tiếp, **không tái sử dụng ID đã có**.

```md
## M-0001 · [YYYY-MM-DD] <tiêu đề ngắn> · #<module-tag>

- **Trạng thái:** ACTIVE
- **Lỗi gì:** <hiện tượng quan sát được>
- **Bối cảnh:** <task/vùng code, file liên quan — cite `path:line#anchor` nếu có>
- **Đã làm gì sai:** <hành động dẫn tới lỗi>
- **Root cause:** <nguyên nhân gốc, không phải triệu chứng>
- **Bài học:** <điều rút ra>
- **Phòng lần sau:** <quy tắc/kiểm tra cụ thể để chặn tái phạm>
```

## Quy tắc điền

- **Trạng thái** đúng một trong: `ACTIVE` · `RESOLVED` · `SUPERSEDED → M-XXXX` (ID đích **phải tồn tại**).
- **Tag** kebab-case, dùng chung không gian tên với `decisions/` và tên trang wiki (`#payments`, `#auth`).
  - Dùng `#luôn-đọc` cho bài học **xuyên suốt mọi module** (vd "không tin memory, luôn đọc source"). Tag này khiến entry được nạp ở **mọi** task — dùng tiết kiệm.
- **Phòng lần sau** phải là **kiểm tra cụ thể làm được**, không phải lời hứa. Xấu: *"cẩn thận hơn"*. Tốt: *"trước khi đổi handler webhook, grep tất cả nơi gọi `retry(` và kiểm idempotency key"*.
- Trích code thì dùng dạng `` `path:line#anchor` `` để `tools/verify.py` bắt được khi code trôi.

`npm run verify` kiểm: ID duy nhất & đúng định dạng, đủ 6 phần, trạng thái hợp lệ, đích `SUPERSEDED` tồn tại, citation còn resolve.
