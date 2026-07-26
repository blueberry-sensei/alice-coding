# Model policy & Fallback

Quy định **model nào được dùng, khi nào, và tụt ưu tiên ra sao** khi lỗi/hết quota. Sub-agent phải luôn bắt đầu từ ưu tiên cao nhất còn khả dụng.

> ⚙️ **Bản generic:** bảng dưới là **policy mặc định của chủ repo** trên máy hiện tại (đã verify qua `opencode auth list` + `opencode models`). Khi init ở máy/tài khoản khác, chạy lại 2 lệnh đó và **cập nhật bảng cho khớp thực tế** — đừng tin cứng.

## Thứ tự ưu tiên (cao → thấp)

| # | Model string (opencode CLI) | Nguồn | Ghi chú |
|---|---|---|---|
| 1 | `opencode/deepseek-v4-flash-free` | OpenCode ZEN (free) | **Mặc định.** Miễn phí, ưu tiên tuyệt đối. |
| 2 | `google/gemini-3.6-flash` | Google AI Studio (free key) | Flash mới nhất |
| 3 | `google/gemini-3.5-flash` | Google | |
| 4 | `google/gemini-3.1-pro-preview` | Google | Pro — mạnh hơn, cho task khó hơn |
| 5 | `google/gemini-3-flash-preview` | Google | |
| 6 | `opencode-go/deepseek-v4-flash` | OpenCode GO (trả phí) | **Cuối cùng** — chỉ khi trên đều hết |

## Quy tắc fallback

1. **Lỗi thông thường** (network, timeout, 5xx, connection reset) → **retry cùng model** 2–3 lần với backoff ngắn. Đừng vội tụt ưu tiên vì một lỗi thoáng qua.
2. **Hết quota / rate limit** (429, "quota exceeded", "resource exhausted", "rate limit") → **tụt xuống model ưu tiên kế tiếp** trong bảng. Không quay lại ưu tiên cao cho tới phiên/task sau (quota thường theo cửa sổ thời gian).
3. **Lỗi auth** (401/403, "invalid api key", "unauthenticated") → **dừng và báo Bệ hạ** cần re-auth (`opencode auth login`). Không tự đổi credential.
4. **Model không tồn tại / bị gỡ** → bỏ qua, tụt tiếp, và ghi chú để cập nhật lại bảng.

## Ghi nhận khi phải fallback

- Nếu một task phải tụt ≥2 bậc, hoặc ưu tiên #1 liên tục hết quota → ghi 1 dòng vào [`changelog`](../changelog/README.md) của module liên quan (hoặc `mistakes/` nếu là vấn đề lặp lại đáng học).
- Report cho Bệ hạ phải nói rõ **cuối cùng model nào đã làm** (vì chất lượng khác nhau theo model).

## Nhắc về chất lượng

Model free/flash (ưu tiên 1–3) nhẹ → **spec càng rõ, chia càng nhỏ càng tốt**, và **review gate của Alice càng phải chặt** (dễ để lại lỗi tinh vi: dead code, API cần lib target, bịa endpoint). Task khó cân nhắc pro (#4) hoặc để Alice tự làm.

## Lệnh dò lại thực tế (chạy khi init / khi nghi ngờ)

```bash
opencode auth list        # provider nào đang auth
opencode models           # model string chính xác đang khả dụng
opencode models google    # lọc theo 1 provider
```
