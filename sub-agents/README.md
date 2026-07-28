# sub-agents — Giao việc cho agent phụ để tiết kiệm token

Nơi chứa kiến thức, bài học, và **cách vận hành** khi Alice (agent chính, đắt) giao phần code cho **sub-agent rẻ** (opencode/gemini/codex...), rồi tự review.

## Triết lý: phân vai

| Vai | Ai | Vì sao |
|---|---|---|
| **Architect + Reviewer** | Alice (model mạnh, đắt) | Viết spec chuẩn, đọc `git diff`, bắt lỗi logic/pattern/security |
| **Implementer** | Sub-agent (model rẻ) | Vòng lặp thử/sai, đọc nhiều file, sửa lint — phần ngốn token nhất |

**Token economics (sự thật):** Alice vẫn tốn token cho spec + đọc diff + review. Chỗ tiết kiệm là **phần iteration** sub-agent làm thay. → Nguyên tắc vàng:

> Viết **1 spec thật kỹ** → sub-agent tự chạy hết → Alice **chỉ đọc `git diff` cuối** (không để transcript sub-agent tràn vào context Alice).

## Index

| File | Nội dung |
|---|---|
| [base-prompt.md](base-prompt.md) | **Base prompt CHUẨN gọi sub-agent** — ép nạp đủ context project, dùng chung mọi lần gọi |
| [models-and-fallback.md](models-and-fallback.md) | Contract Settings → Sub Agents, cách chọn model và fallback khi lỗi/hết quota |
| [delegation-protocol.md](delegation-protocol.md) | Quy trình agent-agnostic: viết spec → chạy → review gate → kỷ luật token |
| [spec-template.md](spec-template.md) | Template task-spec tái dùng (điền vào `## NHIỆM VỤ` của base-prompt) |
| [mcp.md](mcp.md) | Tư vấn capability MCP tùy chọn (browser/docs/DB), không chứa cấu hình provider/model |
| [opencode/README.md](opencode/README.md) | opencode: CLI, cách gọi headless, recipe, gotcha |
| [gemini/README.md](gemini/README.md) | gemini: qua opencode `google/*` hoặc Gemini CLI standalone |

## Khi nào delegate — NGƯỠNG SỐ, không cảm tính

> Bản trước chỉ nói "task cơ học, tốn nhiều vòng lặp". Tiêu chí định tính kiểu đó **luôn thua** thiên kiến tức thời: ngay lúc quyết định, tự làm bao giờ cũng có vẻ nhanh hơn và ít rủi ro hơn — nên thực tế agent gần như **không bao giờ** delegate. Vì vậy ngưỡng phải là con số, giống cách `ALICE.md` mục 4 phân loại LARGE.

**DELEGATE khi thoả ≥3 dấu hiệu:**

1. Đã có **file mẫu đích danh** để bắt chước (pattern rõ, không phải nghĩ mới).
2. Ước tính **≥5 vòng sửa–chạy–sửa** (lint, test, codegen, đổi hàng loạt).
3. **≥4 file** phải sửa theo cùng một khuôn.
4. Definition of done **kiểm được bằng lệnh** (build/test/lint xanh), không cần mắt người phán.
5. **Không** đụng vùng high-risk trong `ALICE.project.md` mục 4.
6. Spec viết được **dưới 40 dòng** mà không bỏ sót gì.

**TỰ LÀM (không delegate) nếu dính bất kỳ điều nào:**

- Đụng auth / payment / migration dữ liệu / xoá dữ liệu / sync đa nguồn.
- Yêu cầu còn mơ hồ, hoặc chính Alice chưa chắc thiết kế nào đúng.
- Cần đọc >10 file mới hiểu đủ để viết spec (chi phí viết spec ≥ chi phí tự làm).
- Chỉ sửa 1–2 file nhỏ.
- Phải đánh đổi kiến trúc / bàn với Bệ hạ.

**Nghi ngờ thì tự làm** — nhưng phải nói rõ trong report là đã cân nhắc và vì sao loại.

## Delegate cho ai — theo agent đang chạy

| Orchestrator | Cách gọi sub-agent | Ghi chú token |
|---|---|---|
| **Claude Code** | Task/Agent tool **native** (`general-purpose`) | Chạy cùng hạng model → **không rẻ đi**. Lợi ích ở đây là **cô lập context** (transcript sub-agent không tràn vào context chính), không phải giá. Muốn rẻ thật thì gọi CLI ngoài. |
| **Codex** | sub-agent/CLI ngoài | |
| **opencode** | `opencode run` headless, chọn slot/model đã bật trong Settings → Sub Agents | Có nhiều model rẻ; chỉ gọi slot đã smoke thật |
| **Gemini CLI** | standalone hoặc qua opencode `google/*` | |

> Đọc kỹ: nếu orchestrator và sub-agent **cùng hạng model**, delegate **không tiết kiệm tiền** — chỉ tiết kiệm *context*. Đừng viện lý do "tiết kiệm token" khi thực tế không tiết kiệm; hãy nói đúng lý do là cô lập context.

## Giới hạn phải biết: sub-agent KHÔNG có não

Sub-agent **không được mount MCP brain**. Nó chạy ở đúng chế độ fallback mô tả trong [`brain/RETRIEVAL.md`](../brain/RETRIEVAL.md) — chỉ đọc file. Hệ quả bắt buộc:

- Orchestrator phải **recall trước**, rồi **nhét kết quả đã chắt lọc vào spec** (ID `M-XXXX`/`D-XXXX` liên quan, trang wiki cần đọc, gotcha đã biết).
- Không được giả định sub-agent tự tìm ra tri thức gián tiếp. Nó không thể.

## An toàn khi delegate

- Sub-agent sửa file thật → luôn làm trên **branch riêng**, commit mốc trước khi giao để dễ `git diff`/rollback.
- Cân nhắc **git worktree** để cô lập workspace sub-agent.
- Không giao thao tác khó đảo ngược (push, xoá vĩnh viễn, đổi setting hệ thống) cho sub-agent tự động.
