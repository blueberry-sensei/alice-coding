# Wiki: <Tên module>

> Copy file này thành `<module>.md`, điền từ **source thật**. Cái gì chưa chắc → ghi "chưa xác minh". Trang phải **tự chứa**.
> Mọi citation vào code dùng dạng `` `path:line#anchor` `` (xem [`README.md`](README.md)) để `tools/verify.py` bắt được khi code trôi.
> Thêm trang này xong → **thêm ngay 1 dòng vào [`ROUTER.md`](ROUTER.md)**, nếu không nó là trang mồ côi.

## Mục đích
<Module này lo việc gì trong hệ thống. 1–3 câu.>

## Bản đồ code (path chính)
| Vai trò | Citation (`path:line#anchor`) | Ghi chú |
|---|---|---|
| Entry / route | `src/.../route.ts:12#handlePost` | |
| Business logic | `...` | |
| Data model / schema | `...` | |
| Integration ngoài | `...` | |

## Contract / API
<Endpoint, input/output, auth/permission, mã lỗi. Xác nhận từ source hiện tại, không từ memory.>

## Data model
<Bảng/collection, field quan trọng, quan hệ, ai là source-of-truth.>

## Luồng chính
<Các bước của flow tiêu biểu, tham chiếu file thực thi.>

## Gotcha & vùng rủi ro
<Điểm dễ sai, quyết định phản trực giác, ràng buộc ngầm, chỗ từng gãy.>

## Liên kết
- Mistakes liên quan: <`M-XXXX` — nêu ID, đừng chép lại nội dung>
- Decisions ràng buộc module này: <`D-XXXX`>
- Changelog: [`changelog/<module>.md`](../changelog/README.md)
- Trang wiki liên quan: <...>

## Chưa xác minh
<Liệt kê phần chưa kịp verify, để lần sau bổ sung — thành thật thay vì bịa.>
