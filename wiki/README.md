# wiki — Kiến thức dự án (tree-shaking + dictionary)

Kiến thức project chia theo **module**, mỗi module **một file tự chứa**. Agent **không đọc cả wiki** — chỉ mở đúng (các) trang khớp vùng bị task tác động. Đó là **tree-shaking**.

> File này là **luật dùng wiki** (thuộc template, `update` sẽ ghi đè).
> Bảng router + dictionary của **project bạn** nằm ở [`ROUTER.md`](ROUTER.md) — file đó thuộc về bạn, `update` **không bao giờ đụng vào**.

## Cách dùng (bắt buộc trước task)

1. Tìm vùng task đụng tới trong [`ROUTER.md`](ROUTER.md) → mở đúng trang đó (và chỉ trang đó nếu đủ).
2. Không chắc thuộc module nào? Tra **Dictionary** trong `ROUTER.md` (thuật ngữ → trang định nghĩa).
3. Trang wiki chỉ là bản đồ — luôn đối chiếu **source thật** mà trang trỏ tới trước khi tin.

## Citation phải có anchor — chống "line rot"

Số dòng **chết sau mọi refactor**. Một trang wiki trỏ `src/payments/refund.ts:210` sẽ âm thầm trỏ sai chỗ ngay lần đầu ai đó chèn 20 dòng phía trên — và agent vẫn tự tin vì "đã đối chiếu source". Vì vậy:

```
`đường/dẫn/file.ts:210#createRefund`
                     ▲    ▲
                  số dòng  anchor: một chuỗi ĐỊNH DANH có thật trong file
                           (tên hàm/class/const/route — không khoảng trắng)
```

- **Bắt buộc dùng dạng có `#anchor`** cho mọi citation trỏ vào code trong `wiki/`, `mistakes/`, `decisions/`.
- `python tools/verify.py` sẽ: tìm anchor trong file → nếu nằm ở dòng khác thì báo **trôi dòng**; `python tools/verify.py --fix` **tự sửa lại số dòng**. Nếu anchor **không còn tồn tại** → báo ERROR (code đã bị đổi tên/xoá → trang wiki đang nói dối).
- Trỏ vào file không phải code (config, md) thì dùng `path` trần, không cần dòng.

## Convention thêm module

- Tên file kebab-case theo **ranh giới nghiệp vụ**, không theo thư mục code (`payments.md`, `auth.md`, `hotel-bookings.md`).
- Mỗi trang **tự chứa**: đọc một mình vẫn hiểu, không buộc phải đọc trang khác.
- Trang quá to = module đang ôm quá nhiều việc → tách nhỏ.
- Đổi behavior/contract của module → cập nhật trang tương ứng **trong cùng task**.
- **Thêm trang mới → thêm dòng vào [`ROUTER.md`](ROUTER.md) ngay.** `tools/verify.py` báo ERROR nếu có trang wiki không nằm trong router (trang mồ côi — retrieval sẽ không bao giờ tìm ra nó), hoặc router trỏ tới trang không tồn tại.

## Liên kết chéo

Trang wiki nên trỏ tới ID của các trụ cột khác thay vì chép lại nội dung:
`Xem M-0007` (mistakes) · `Xem D-0003` (decisions) · [`changelog/<module>.md`](../changelog/README.md).
