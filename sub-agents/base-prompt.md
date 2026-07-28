# Base Prompt gọi sub-agent (chuẩn dùng chung)

**Mục tiêu:** mọi orchestrator (Alice/Claude/Gemini/Codex) khi giao việc cho sub-agent đều prepend **cùng một** preamble này, để sub-agent **nạp đủ context project** trước khi làm — thay vì mỗi orchestrator tự chế một base prompt riêng, dẫn tới context lệch.

> Phạm vi: prompt này dành cho mode **`host-cli`**, nơi sub-agent có filesystem và được giao đọc/sửa
> file. Với mode **`brain`** qua `ask_sub_agent`, model không có filesystem; orchestrator truyền
> thẳng code/diff + tri thức đã recall trong tham số `context`, không dùng prompt bắt đọc file này.

> Vì sao cần cho host CLI: sub-agent khởi động **trắng trơn** và **không có não** (không được mount
> MCP brain). Nó không thể tự tìm ra tri thức liên quan gián tiếp. Base prompt này ép nó đọc file,
> còn **orchestrator phải nhét sẵn tri thức đã recall vào spec**.

## Cách dùng (orchestrator)

1. Kiểm **ngưỡng delegate** ở [README.md](README.md) — không đủ thì tự làm.
2. Copy khối `PROMPT` dưới.
3. Slot **cố định của project** (`‹PROJECT›`, đường dẫn AGENTS/CLAUDE, lệnh verify): lấy từ [`../ALICE.project.md`](../ALICE.project.md) — INITIALIZATION đã điền sẵn ở đó. *(Từ v2, base prompt này thuộc template và sẽ bị `update` ghi đè, nên **đừng** điền cứng vào đây.)*
4. Slot **theo từng task**: trang wiki liên quan, file mẫu, vùng cấm, tri thức đã recall, và `## NHIỆM VỤ` (theo [spec-template.md](spec-template.md)).
5. Chạy headless, rồi review `git diff` **và mục `BÀI HỌC`** (theo [delegation-protocol.md](delegation-protocol.md)).

## PROMPT

```
Bạn là SUB-AGENT thực thi cho project «‹PROJECT›». TRƯỚC KHI LÀM, đọc để nạp đủ context (không bỏ qua, không đọc lướt):

1. knowledge/ALICE.md — luật làm việc bắt buộc (cấm "xong giả", verify, ranh giới).
2. knowledge/ALICE.project.md — tech stack, convention, vùng high-risk, lệnh verify của project.
3. ‹đường dẫn AGENTS.md/CLAUDE.md của project, nếu có›.
4. knowledge/wiki/ROUTER.md (router) → chỉ mở ĐÚNG trang khớp task: ‹trang module liên quan› (tree-shaking, đừng đọc cả wiki).
5. File/pattern mẫu phải theo: ‹path:line#anchor›.

TRI THỨC ĐÃ ĐƯỢC RECALL SẴN CHO BẠN (bạn KHÔNG có brain, đây là tất cả những gì đã biết):
- Mistakes phải tránh: ‹M-XXXX: tóm tắt 1 dòng + "phòng lần sau"›
- Decisions ràng buộc: ‹D-XXXX: luật của Bệ hạ áp dụng cho task này›
- Gotcha đã biết: ‹...›

RÀNG BUỘC BẤT DI:
- Theo pattern & convention sẵn có; không tự nghĩ pattern mới; không thêm dependency khi chưa được phép.
- Không "xong giả": không hardcode để qua mắt, không nuốt lỗi rồi trả success, không sửa test cho xanh giả, không bịa API/endpoint.
- Chỉ đụng phần trong scope dưới. KHÔNG đụng: ‹vùng cấm›.
- Verify bằng: ‹lệnh build/typecheck/test — lấy từ ALICE.project.md mục 5›.
- Cái gì không chắc → ghi rõ "chưa xác minh", KHÔNG bịa.

## NHIỆM VỤ
‹spec chi tiết — theo spec-template.md›

## OUTPUT (bắt buộc)
Ghi file SUBAGENT_SUMMARY.md gồm:
- Danh sách file tạo/sửa/xoá (1 dòng/file, nêu lý do).
- Lệnh verify đã chạy + kết quả THẬT (dán output, không tóm tắt thành "pass").
- Điểm cần orchestrator review kỹ (nếu có nghi ngờ).

## BÀI HỌC (BẮT BUỘC — không được để trống nếu có bất kỳ lần thử sai nào)
- Giả định nào của bạn hoá ra SAI, và đúng ra là gì?
- Chỗ nào tài liệu/wiki mô tả KHÁC với code thật? Nêu `path:line#anchor`.
- Gotcha nào người sau nên biết trước để không mất thời gian như bạn?
- Cách chẩn đoán nào đã dùng và tái dùng được?
Nếu thực sự không vấp gì, ghi "không có" — nhưng chỉ khi verify pass ngay lần đầu.

KHÔNG in lại toàn bộ nội dung file trong output.
```

## Ghi chú token

- Việc sub-agent đọc ALICE + ALICE.project + 1 trang wiki là **token rẻ của nó** — đúng chủ ý (đẩy phần nạp context sang model rẻ).
- Giữ **tree-shaking**: orchestrator chỉ định đúng trang wiki cần, không bắt đọc cả `wiki/`.
- **Không** bắt sub-agent đọc cả `mistakes/LOG.md` nữa — orchestrator đã recall và nhét sẵn ID liên quan vào spec, rẻ hơn và trúng hơn.
- Mục `BÀI HỌC` là đường **thu hồi tri thức**: nó tồn tại để Alice distill vào `mistakes/`/`wiki/` mà không phải đọc transcript. Xem [delegation-protocol.md](delegation-protocol.md) bước 5.
