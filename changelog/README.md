# changelog — Nhật ký thay đổi theo module

**1 file / module hoặc microservice.** Mỗi file ghi lại các thay đổi đã làm ở module đó, **compact**, kèm khó khăn gặp phải và mistakes liên quan.

> Bản generic: chưa có file module nào. Init tạo `<module>.md` cho từng module, backfill vài mốc lớn từ `git log`.

## Convention

- Tên file khớp tên module trong [Wiki Router](../wiki/ROUTER.md): `payments.md`, `hotel-bookings.md`, `auth.md`...
- Entry mới **lên đầu** file (mới nhất trên cùng).
- **Compact**: mô tả kết quả, không chép diff.
- Mỗi entry theo [`_TEMPLATE.md`](_TEMPLATE.md).
- Ghi changelog **sau khi verify xong**, cùng task với thay đổi code (theo `ALICE.md` mục 5).

## Format entry

- **Ngày** + tóm tắt thay đổi (1–2 dòng).
- **Khó khăn** gặp phải (nếu có).
- **Liên quan**: nêu **ID** `M-XXXX` ([mistakes](../mistakes/README.md)) và `D-XXXX` ([decisions](../decisions/README.md)) — trỏ ID, không chép lại nội dung.
- **Trạng thái** (done / partial / cần theo dõi).
- Con trỏ: branch/commit/PR nếu có.

> Changelog là trụ cột **append-only có chủ đích** (nhật ký lịch sử, không sửa lại quá khứ). Chống phình bằng cách giữ entry compact và gộp file khi module bị gộp — không bằng `SUPERSEDED` như `mistakes/`/`decisions/`.
