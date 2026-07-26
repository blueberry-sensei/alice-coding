# context — Ký ức xuyên session

Nơi lưu **digest các phiên trao đổi** với Bệ hạ, compact nhưng giữ **100% điều đáng nhớ** (quyết định, lý do, trạng thái, luồng còn mở). Mục tiêu: một session mới đọc vào là **sống lại đúng bối cảnh**.

## Khác gì các trụ cột kia?

| Trụ cột | Trả lời câu hỏi |
|---|---|
| `wiki/` | Hệ thống **đang** thế nào? |
| `changelog/` | Code **đã đổi** gì? |
| `mistakes/` | Alice **đã sai** gì? |
| `decisions/` | Bệ hạ **muốn** thế nào? (luật bền, xuyên phiên) |
| **`context/`** | **Phiên đó đã diễn ra thế nào** — bàn gì, chốt gì, còn treo gì (mạch truyện, gắn với thời điểm) |

> Ranh giới hay nhầm: một câu Bệ hạ chốt *"từ giờ đừng dùng barrel export"* → vào **`decisions/`** (luật bền, phải tra được mãi mãi), **không phải** context. Context chỉ ghi *"phiên này đã chốt D-0007"*. Luật bền chôn trong digest = chết chìm theo phiên.

## Luật

1. Đầu session, đọc [`INDEX.md`](INDEX.md) → nạp (các) digest gần nhất liên quan.
2. Cuối phiên có trao đổi/quyết định đáng nhớ → tạo **1 file digest mới** theo [`_TEMPLATE.md`](_TEMPLATE.md), tên `YYYY-MM-DD-<chủ-đề>.md`, rồi thêm dòng vào `INDEX.md` (mới nhất trên cùng).
3. **Compact**: ghi quyết định + lý do + trạng thái, không chép nguyên hội thoại.
4. Không ghi secret vào context.
5. Digest **trỏ ID** (`M-0007`, `D-0003`) thay vì chép lại nội dung trụ cột khác.

`tools/verify.py` kiểm hai chiều: mọi file digest phải có dòng trong `INDEX.md`, và mọi dòng `INDEX.md` phải trỏ file có thật.

## Checkpoint chống auto-compact

Context có thể bị **auto-compact** giữa chừng → mất chi tiết. Vì vậy **đừng đợi cuối phiên**.

**Ghi checkpoint ngay khi chạm một trong các mốc sau** (tiêu chí cụ thể thay cho cảm tính "đạt mốc"):

- Vừa chốt xong một **quyết định thiết kế** ảnh hưởng phần việc còn lại.
- Vừa **verify pass** một phần lớn (build/test/smoke xanh) — để sau compact không phải làm lại.
- Sắp bắt đầu một nhánh việc **dài** (nhiều file, nhiều vòng lặp).
- Đã trao đổi **>10 lượt** trong cùng một task mà chưa có checkpoint nào.
- Bệ hạ vừa cung cấp **thông tin không có trong repo** (số liệu, ràng buộc bên ngoài, ngữ cảnh nghiệp vụ).

Checkpoint là **cập nhật đè lên digest của phiên hiện tại**, không tạo file mới mỗi lần — một phiên một file.

## Vì sao cần

Agent không có trí nhớ giữa các session, và context trong phiên có thể bị compact bất cứ lúc nào. `context/` là **"bộ nhớ ngoài" trên đĩa** để mọi phiên (kể cả agent khác) tiếp nối đúng, thay vì hỏi lại từ đầu hoặc suy diễn sai.
