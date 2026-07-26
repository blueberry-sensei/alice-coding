# Wiki Router — vùng tác động → trang

> **File này thuộc về project của bạn**, không thuộc template. `python tools/update.py` **không bao giờ ghi đè** nó.
> [`INITIALIZATION.md`](../INITIALIZATION.md) điền lần đầu từ codebase thật; sau đó mỗi lần thêm trang wiki là thêm một dòng ở đây.

## Router — task đụng gì → đọc trang nào

| Task đụng gì | Trang phải đọc |
|---|---|
| <!-- ‹vd: Thanh toán / checkout› --> | <!-- `payments.md` --> |

<!-- Chưa đặc tả. INITIALIZATION sẽ điền từ module map thật. -->

## Dictionary — thuật ngữ → nơi định nghĩa

| Thuật ngữ / khái niệm | Nghĩa ngắn | Trang |
|---|---|---|
| <!-- ‹vd: "wholesale amount"› --> | <!-- ‹1 dòng› --> | <!-- `payments.md` --> |

<!-- Chưa đặc tả. -->

---

**Kiểm tra:** `python tools/verify.py` bắt lỗi hai chiều —
trang `wiki/*.md` không có mặt trong bảng Router (mồ côi → retrieval không tìm ra),
và dòng Router trỏ tới trang không tồn tại (dangling).
