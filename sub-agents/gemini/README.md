# Agent: gemini

Gemini có thể dùng theo **2 cách**. Ở máy chủ repo hiện tại, cách (A) đã sẵn sàng.

## (A) Qua opencode, provider `google` — ĐANG DÙNG ĐƯỢC

Google (AI Studio API key free) đã auth trong opencode → gọi gemini y hệt opencode run, chỉ đổi `-m`:

```bash
opencode run -m google/gemini-3.6-flash --agent build --auto --dir "<path>" "$(cat spec.md)" > run.log 2>&1
```

Model cho đường OpenCode phải đối chiếu bằng catalog thật của OpenCode. Model cho Gemini CLI lấy từ
slot Gemini CLI đang bật ở Brain → Settings → Sub Agents; không dùng bảng model tĩnh trong repo.

→ Ưu điểm: dùng chung toàn bộ recipe/gotcha của [opencode](../opencode/README.md), không phải học tool mới. **Khuyến nghị dùng cách này** trừ khi cần tính năng riêng của Gemini CLI.

## (B) Gemini CLI standalone — TÙY CHỌN (chưa cài)

Google có Gemini CLI riêng (agent độc lập). Chỉ cài nếu Bệ hạ muốn một agent tách biệt khỏi opencode.

Khi init/cài, điền theo khung như [opencode/README.md](../opencode/README.md):
- [ ] Lệnh cài + auth (API key AI Studio / Vertex)?
- [ ] Lệnh chạy prompt **non-interactive** (tương đương `opencode run`)?
- [ ] Cờ auto-approve permission / chỉ định model / working dir / output format?
- [ ] Có tự đọc context repo (AGENTS.md/CLAUDE.md) không?
- [ ] Recipe đầy đủ + smoke test.

## Lưu ý

- Gemini Flash hợp task cơ học; Pro hợp task khó hơn. Dùng đúng alias/model đã smoke trong registry.
- Quy trình chung (viết spec, review gate, kỷ luật token) **dùng lại nguyên** [delegation-protocol.md](../delegation-protocol.md).
