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

**Sự kiện do chính agent bóc.** Brain không chạy LLM để hiểu entry; nó nhớ đúng những mệnh đề mà
entry mang theo. Entry mới phải có khối `- **Sự kiện:**` (verify `C10` cảnh báo nếu thiếu) — mỗi dòng con một mệnh đề trọn
nghĩa, định danh để trong `backtick` (xem [`SYNC.md`](SYNC.md) mục *Sự kiện*). Entry cũ không có khối
đó thì sync tự tách mỗi bullet/đoạn thành một sự kiện.

### 3. PRUNE — dọn rác (bước mới, đừng bỏ)

> Không có bước này thì kho tri thức chỉ phình. Ba trong bốn trụ cột là append-only, nên **thêm mà không dọn = recall tệ dần**: SAG sẽ trả về 5 event gần giống nhau và tri thức đúng bị loãng.

Rà và xử lý:

- **Trùng root cause:** nhiều entry `mistakes` cùng một nguyên nhân → **gộp** thành một entry đầy đủ nhất; các entry kia đổi `Trạng thái: SUPERSEDED → M-XXXX`.
- **Đã fix tận gốc:** entry có guard/test chặn tái phạm → `RESOLVED`, ghi rõ guard nào.
- **Bệ hạ đổi ý:** decision cũ mâu thuẫn decision mới → cũ thành `SUPERSEDED → D-XXXX`. **Không xoá.**
- **Hai entry ACTIVE mâu thuẫn:** đây là lỗi dữ liệu, phải xử ngay trong task này — cái mới hơn thắng, cái cũ thành `SUPERSEDED`.
- **Wiki nói sai về code:** `verify` báo anchor mất → sửa nội dung trang, không chỉ sửa số dòng.
- **Trang wiki phình:** module ôm quá nhiều việc → tách trang, cập nhật `ROUTER.md`.

`npm run verify` in cảnh báo `C7` khi vượt ngưỡng đọc-hết-được — coi cảnh báo đó là **lệnh prune**, không phải thông tin tham khảo.

### 4. Verify
```bash
npm run verify:fix     # --fix tự nắn lại citation trôi dòng
```
Phải **0 ERROR**. Đây cũng là gate của bước 5.

### 5. Sync não
```bash
npm run sync
```
`sync.py` **tự chạy verify trước**: entry/file còn ERROR bị **giữ lại** (não giữ bản cũ, sync in `= HELD …`), phần sạch vẫn vào não. Giữ lại không phải xong — bước 4 vẫn phải 0 ERROR. Không có não (brain disabled) thì bỏ bước này, **nhưng vẫn phải chạy verify**.

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

**Ghi file là rẻ → làm ngay. Sync gộp lại cuối task.** Sync chỉ gửi entry đã đổi và chỉ chạy embedding, nhưng vẫn không cần chạy sau mỗi turn.

## Nguyên tắc
- **Tự chủ, không đợi nhắc** — ngang bổn phận ở `ALICE.md` mục 9a. Bỏ ghi tri thức = task **chưa** hoàn thành.
- **Không bịa để lấp đầy.** Không có bài học thật thì thôi.
- **Không xoá, chỉ đổi trạng thái.** Xoá là mất lịch sử vì-sao.
- **File là chân lý:** ghi vào file trước, rồi sync — không ghi thẳng vào não (não là index dẫn xuất).
- Đây cũng là đường **rebuild an toàn:** tri thức nằm ở file nên `npm run sync:rebuild` luôn dựng lại được não (bản cũ chỉ bị xoá khi bản mới đã `ready`).
