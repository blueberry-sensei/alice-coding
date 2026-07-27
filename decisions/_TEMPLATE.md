# Decision entry template

Copy khối dưới, dán lên **đầu** `LOG.md`. ID lấy số kế tiếp, **không tái sử dụng ID đã có**.

```md
## D-0001 · [YYYY-MM-DD] <tiêu đề ngắn, đọc là hiểu luật> · #<tag>

- **Trạng thái:** ACTIVE
- **Loại:** sở-thích | quyết-định | nghiệp-vụ | ranh-giới | hướng-đã-loại
- **Luật:** <phát biểu dứt khoát, ở dạng ra lệnh — "luôn ...", "không bao giờ ...">
- **Vì sao:** <lý do/đánh đổi Bệ hạ nêu. Không có thì ghi "Bệ hạ không nêu lý do">
- **Áp dụng khi:** <phạm vi cụ thể — module/tình huống nào. Tránh "mọi nơi" nếu không thật sự vậy>
- **Nguồn:** phiên YYYY-MM-DD — Bệ hạ: "<trích nguyên văn ngắn>"
```

## Quy tắc điền

- **Trạng thái** đúng một trong: `ACTIVE` · `SUPERSEDED → D-XXXX` · `RETIRED`.
  - `SUPERSEDED → D-XXXX`: Bệ hạ đổi ý, có luật mới thay thế (ID đích **phải tồn tại**).
  - `RETIRED`: không còn áp dụng và **không** có luật thay thế (vd module đã bị xoá).
- **Tag** kebab-case, dùng chung không gian tên với `mistakes/` và tên trang wiki (`#payments`, `#convention`, `#auth`).
- **Luật** viết ở thể mệnh lệnh để turn sau đọc là thi hành được ngay — không viết kiểu tường thuật ("Bệ hạ có vẻ thích...").
- **Nguồn** bắt buộc có trích dẫn. Không trích được = đang bịa → đừng ghi.

`npm run verify` kiểm: ID duy nhất & đúng định dạng, đủ 6 trường, trạng thái hợp lệ, đích `SUPERSEDED` tồn tại.
