# mistakes — Nhật ký lỗi & bài học

Nơi Alice ghi lại **mọi lỗi đã mắc, giả định sai, near-miss** để không tái phạm. Đây là bộ nhớ đau thương của agent.

## Luật đọc (phân tầng — thay cho "đọc toàn bộ")

> Bản trước bắt "đọc TOÀN BỘ `LOG.md` trước mọi task". Luật đó **không sống nổi qua 6 tháng**: file phình tới vài nghìn dòng thì agent sẽ đọc lướt — tức là luật bị vi phạm âm thầm, tệ hơn không có luật. Thay bằng phân tầng, và **giữ file đủ nhỏ để tầng 1 luôn đọc hết được**.

1. **Luôn đọc hết:** mọi entry `ACTIVE` có tag khớp vùng task đụng tới, **cộng** mọi entry gắn `#luôn-đọc` (bài học xuyên suốt, không thuộc module nào).
2. **Đọc thêm khi task là LARGE** (theo [`ALICE.md`](../ALICE.md) mục 4) hoặc đụng vùng high-risk: toàn bộ entry `ACTIVE`, bất kể tag.
3. **Không dùng làm căn cứ:** entry `RESOLVED` / `SUPERSEDED` — chỉ mở khi cần truy lịch sử.

Nếu `LOG.md` phình tới mức tầng 2 không đọc nổi trong một lần → đó là tín hiệu phải **prune/gộp** (xem [`brain/KNOWLEDGE.md`](../brain/KNOWLEDGE.md)), không phải tín hiệu để bỏ đọc. `tools/verify.py` sẽ cảnh báo khi vượt ngưỡng.

## Luật ghi

1. Gặp incident / giả định sai / cách chẩn đoán tái dùng được → **thêm 1 entry** theo [`_TEMPLATE.md`](_TEMPLATE.md), **ngay trong task đó**.
2. Entry mới thêm **lên đầu** `LOG.md`.
3. **Không bịa lỗi** để lấp đầy. Chưa có thì để trống.
4. Task đụng vùng từng có lỗi → đọc entry liên quan **trước khi** đề xuất thay đổi.
5. Lỗi do **sub-agent** gây ra cũng ghi vào đây — Alice distill từ mục `BÀI HỌC` trong `SUBAGENT_SUMMARY.md` (xem [`sub-agents/delegation-protocol.md`](../sub-agents/delegation-protocol.md)).

## Format (bắt buộc đủ 6 phần + ID + trạng thái)

- **ID `M-XXXX`** — ổn định, không đổi, không tái sử dụng. Để wiki/changelog/decisions link tới.
- **Trạng thái** — `ACTIVE` · `RESOLVED` · `SUPERSEDED → M-XXXX`.
- **Lỗi gì** — hiện tượng quan sát được.
- **Bối cảnh** — task/vùng code, tag module.
- **Đã làm gì sai** — hành động dẫn tới lỗi.
- **Root cause** — nguyên nhân gốc (không phải triệu chứng).
- **Bài học** — điều rút ra.
- **Phòng lần sau** — quy tắc/kiểm tra cụ thể để chặn tái phạm.

Giữ mỗi entry **compact**.

## Vòng đời entry — chống rác

| Tình huống | Làm gì |
|---|---|
| Đã fix tận gốc, không thể tái diễn (có test/guard chặn) | Đổi trạng thái → `RESOLVED`, ghi rõ guard nào chặn |
| Hiểu lại root cause, entry cũ sai/nông | Thêm entry mới, entry cũ → `SUPERSEDED → M-XXXX` |
| Nhiều entry cùng một root cause | **Gộp** thành 1 entry đầy đủ, các entry kia → `SUPERSEDED` trỏ về nó |
| Module đã bị xoá khỏi codebase | → `RESOLVED`, ghi lý do "module đã gỡ" |

**Không xoá entry.** Xoá là mất lịch sử vì-sao; đổi trạng thái mới là cách đúng. Retrieval đã được dạy bỏ qua entry không `ACTIVE` ([`brain/RETRIEVAL.md`](../brain/RETRIEVAL.md)).
