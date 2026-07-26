# Task-Spec Template

Copy khối dưới mỗi lần giao việc cho sub-agent. Chỗ nào bỏ trống là chỗ sub-agent sẽ đoán (và đoán sai).

```md
# TASK: <tên ngắn>

## Goal
<1–2 dòng: kết quả mong muốn, đo được>

## Repo context
- Working dir: <đường dẫn tuyệt đối>
- Branch: <branch hiện tại — đã tạo sẵn>
- Stack & convention: <lấy từ ALICE.md của project>
- Pattern phải theo: xem <file mẫu:dòng> — copy cách nó làm, đừng tự nghĩ pattern mới.

## Changes
1. <thay đổi 1: file + mô tả chính xác>
2. <thay đổi 2>

## Constraints (KHÔNG vi phạm)
- Theo convention repo (lint/format/ngôn ngữ code).
- KHÔNG thêm dependency mới trừ khi liệt kê ở đây.
- KHÔNG đụng: <danh sách file/thư mục cấm>.
- <ràng buộc đặc thù project, vd prefix CSS, không đổi config build...>

## Definition of Done
- [ ] <tiêu chí 1>
- [ ] <lệnh verify của project> pass (vd typecheck/build/lint/test).
- [ ] <smoke nếu ảnh hưởng runtime/UI>

## Output required
Ghi `SUBAGENT_SUMMARY.md`:
- Danh sách file tạo/sửa/xoá (1 dòng/ file, nêu lý do).
- Lệnh verify đã chạy + kết quả.
- Điểm cần Alice review kỹ (nếu có nghi ngờ).
KHÔNG in lại toàn bộ nội dung file trong output.
```

## Ví dụ (khung — thay bằng bối cảnh project thật)

```md
# TASK: Thêm helper slugify

## Goal
Tạo `slugify(input): string` biến chuỗi thành URL slug (lowercase, bỏ dấu, thay space/_ bằng '-', gộp '-', trim '-').

## Repo context
- Working dir: <path>
- Branch: feat/slugify-helper
- Stack: <từ ALICE.md>
- Pattern: đặt cùng chỗ các util hiện có (xem <utils dir>).

## Changes
1. Tạo file util slugify + export named `slugify`.

## Constraints
- Ngôn ngữ thuần, không thêm dependency.
- Chỉ tạo 1 file.

## Definition of Done
- [ ] 3 ví dụ đúng: "Đà Nẵng"→"da-nang", "  A__B "→"a-b", "x: 1$"→"x-1".
- [ ] <lệnh typecheck/test> pass.

## Output
Ghi SUBAGENT_SUMMARY.md.
```
