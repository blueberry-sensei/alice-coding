# brain / KNOWLEDGE — Routine `/knowledge` (tự chủ cải thiện)

Tiêu chí **C — tự chủ động cải thiện bản thân**. Routine **portable** (mọi agent chạy được), biến mỗi phiên làm việc thành tri thức tái dùng, rồi cập nhật não.

> Gọi thế nào: đây là **quy trình**, không khoá vào 1 agent. Claude Code có thể bọc thành slash command (`.claude/commands/knowledge.md` trỏ về file này). Codex/Gemini/opencode: *"chạy routine brain/KNOWLEDGE.md"*.

## Quy trình

### 1. Review phiên hiện tại
Đã đổi gì, học được gì, vấp gì, Bệ hạ đã chốt/bác gì.

### 2. Distill vào đúng trụ cột
Ghi *thật*, không bịa; đối chiếu source.

| Phát sinh | Ghi vào |
|---|---|
| Đổi behavior/contract/source-of-truth | [`wiki/`](../wiki/README.md) (+ [`ROUTER.md`](../wiki/ROUTER.md) nếu thêm trang) |
| Lỗi / near-miss / giả định sai / cách chẩn đoán tái dùng | [`mistakes/LOG.md`](../mistakes/README.md) — `M-XXXX` |
| Bệ hạ nêu sở thích / chốt hướng / bác hướng / luật nghiệp vụ | [`decisions/LOG.md`](../decisions/README.md) — `D-XXXX` **(đáng lẽ đã ghi ngay lúc phát sinh, đây chỉ là lưới hứng)** |
| Thay đổi code | [`changelog/<module>.md`](../changelog/README.md) |
| Mạch truyện phiên, việc còn treo | digest [`context/`](../context/README.md) + `INDEX.md` |

### 3. PRUNE — dọn rác (bước mới, đừng bỏ)

> Không có bước này thì kho tri thức chỉ phình. Ba trong bốn trụ cột là append-only, nên **thêm mà không dọn = recall tệ dần**: SAG sẽ trả về 5 event gần giống nhau và tri thức đúng bị loãng.

Rà và xử lý:

- **Trùng root cause:** nhiều entry `mistakes` cùng một nguyên nhân → **gộp** thành một entry đầy đủ nhất; các entry kia đổi `Trạng thái: SUPERSEDED → M-XXXX`.
- **Đã fix tận gốc:** entry có guard/test chặn tái phạm → `RESOLVED`, ghi rõ guard nào.
- **Bệ hạ đổi ý:** decision cũ mâu thuẫn decision mới → cũ thành `SUPERSEDED → D-XXXX`. **Không xoá.**
- **Hai entry ACTIVE mâu thuẫn:** đây là lỗi dữ liệu, phải xử ngay trong task này — cái mới hơn thắng, cái cũ thành `SUPERSEDED`.
- **Wiki nói sai về code:** `verify` báo anchor mất → sửa nội dung trang, không chỉ sửa số dòng.
- **Trang wiki phình:** module ôm quá nhiều việc → tách trang, cập nhật `ROUTER.md`.

`python tools/verify.py` in cảnh báo `C7` khi vượt ngưỡng đọc-hết-được — coi cảnh báo đó là **lệnh prune**, không phải thông tin tham khảo.

### 4. Verify
```bash
python tools/verify.py --fix     # --fix tự nắn lại citation trôi dòng
```
Phải **0 ERROR**. Đây cũng là gate của bước 5.

### 5. Sync não
```bash
python brain/sync/sync.py
```
`sync.py` **tự chạy verify trước và từ chối chạy nếu còn ERROR** — nên bước 4 và 5 thực chất là một cổng duy nhất. Không có não (brain disabled) thì bỏ bước này, **nhưng vẫn phải chạy verify**.

### 6. Report ngắn
Đã thêm/sửa trụ cột nào (nêu ID), đã prune gì, verify sạch chưa, sync (+/~/-), phần còn bỏ ngỏ.

## Nhịp chạy — khi nào gọi routine này

| Thời điểm | Làm gì |
|---|---|
| **Ngay trong turn** Bệ hạ nêu sở thích/quyết định | Ghi `decisions/` — **không đợi routine này** |
| Ngay khi gặp lỗi/near-miss | Ghi `mistakes/` — không đợi |
| Chạm mốc checkpoint (xem [`context/README.md`](../context/README.md)) | Cập nhật digest phiên |
| **Cuối mỗi task** | Chạy đủ 6 bước trên |
| Cuối phiên dài | Chạy lại bước 3 (prune) + 4 + 5 |

**Ghi file là rẻ → làm ngay. Sync là đắt → gộp lại cuối task.** Đừng sync sau mỗi turn.

## Nguyên tắc
- **Tự chủ, không đợi nhắc** — ngang bổn phận ở `ALICE.md` mục 9a. Bỏ ghi tri thức = task **chưa** hoàn thành.
- **Không bịa để lấp đầy.** Không có bài học thật thì thôi.
- **Không xoá, chỉ đổi trạng thái.** Xoá là mất lịch sử vì-sao.
- **File là chân lý:** ghi vào file trước, rồi sync — không ghi thẳng vào não (não là index dẫn xuất).
- Đây cũng là đường **rebuild an toàn:** tri thức nằm ở file nên `sync.py --rebuild` luôn dựng lại được não.
