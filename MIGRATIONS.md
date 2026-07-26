# MIGRATIONS — Việc phải làm tay khi lên version mới

`python tools/update.py` tự chép file template và tự phát hiện các bước phải làm tay, rồi in ra ở cuối. File này giải thích **vì sao** và **làm thế nào** cho từng bước đó.

Quy ước version: **semver**. MAJOR đổi = có breaking change bắt buộc đọc mục tương ứng dưới đây.

---

## 2.1.0 — Đổi tên repo, engine riêng, launcher tự lấy nguồn

**Không breaking với tri thức của bạn.** `update` chép file template như thường; các file instance không bị chạm.

### Vì sao

Stack cũ clone engine retrieval từ repo của bên thứ ba. Từ bản này, ALICE CODING chạy trên hai repo riêng — [`alice-core`](https://github.com/blueberry-sensei/alice-core) (engine) và [`alice-brain`](https://github.com/blueberry-sensei/alice-brain) (ứng dụng) — và repo template đổi tên thành [`alice-coding`](https://github.com/blueberry-sensei/alice-coding).

### Việc phải làm tay

| # | Việc | Cách làm |
|---|---|---|
| 1 | Dựng lại stack trên nguồn mới | `npm run uninstall -- --yes` rồi `npm run brain`. Launcher tự clone hai repo mới. **Dữ liệu não bị xoá** → phải `python brain/sync/sync.py --rebuild` sau đó. File tri thức là source-of-truth nên không mất gì. |
| 2 | `.env` cũ có `SAG_PATH` | Xoá dòng đó khỏi `brain/stack/.env`. Nó không còn được đọc. Muốn build từ source trên máy thì dùng `ALICE_APP_PATH` / `ALICE_CORE_PATH`. |
| 3 | Remote git trỏ tên cũ | Nếu bạn từng đặt `ALICE_TEMPLATE_REPO`, đổi sang `https://github.com/blueberry-sensei/alice-coding`. Không đặt gì thì mặc định đã đúng. |

### Tự động

- Launcher tự clone `alice-brain` + `alice-core` (ghim `main`) vào `brain/stack/`; không cần chuẩn bị gì trên máy sạch.
- `npm run uninstall` đã biết dọn hai thư mục clone mới.
- Ngôn ngữ prompt trích xuất nhận `en` | `vi` (bỏ `zh`).

### Kiểm tra đã xong

```bash
python tools/verify.py
```

---

## 2.0.0 — Tách template/instance, forcing function, trụ cột thứ 6

**Breaking.** Đây là bản đầu tiên có đường nâng cấp; các bản sau sẽ migrate được tự động từ đây.

### Vì sao

v1 có 5 lỗ hổng kiến trúc khiến hệ thống degrade âm thầm khi dùng lâu: không có đường nâng cấp, không có forcing function ngoài context, tri thức chỉ append nên thành rác, không có chỗ chứa sở thích/quyết định của Bệ hạ, và ngưỡng delegate quá mơ hồ để dùng.

### Việc phải làm tay

| # | Việc | Cách làm |
|---|---|---|
| 1 | Chuyển phụ lục project khỏi `ALICE.md` | Mở `ALICE.md` bản cũ (git history), copy phần **"Phụ lục đặc thù project"** vào [`ALICE.project.md`](ALICE.project.md) theo đúng 7 mục. `ALICE.md` từ nay thuần luật, `update` sẽ ghi đè. |
| 2 | Chuyển bảng router khỏi `wiki/README.md` | Copy 2 bảng **Router** + **Dictionary** sang [`wiki/ROUTER.md`](wiki/ROUTER.md). |
| 3 | Thêm ID + Trạng thái cho `mistakes/LOG.md` | Mỗi entry đổi heading thành `## M-0001 · [YYYY-MM-DD] tiêu đề · #tag` và thêm dòng `- **Trạng thái:** ACTIVE`. Đánh số theo thứ tự thời gian tăng dần. |
| 4 | Dựng trụ cột `decisions/` | Rà `context/` cũ, tách các **luật bền** của Bệ hạ (sở thích, quy ước, hướng đã loại) thành entry `D-XXXX` trong `decisions/LOG.md`. Digest context chỉ giữ mạch truyện. |
| 5 | Thêm `#anchor` vào citation | Mọi `` `path:line` `` trong `wiki/` đổi thành `` `path:line#tênHàm` ``. Chạy `python tools/verify.py` để biết cái nào còn thiếu (WARN) hoặc đã trỏ sai (ERROR). |
| 6 | Sync lại não | `.sync-state.json` lên schema v2 → chạy `python brain/sync/sync.py --rebuild` một lần. An toàn vì file mới là source-of-truth. |

### Tự động

- `update` tạo sẵn khung rỗng cho `ALICE.project.md`, `wiki/ROUTER.md`, `decisions/` nếu chưa có.
- `sync.py` tự chặn nếu state cũ schema, kèm hướng dẫn `--rebuild`.
- `verify.py` chỉ ra chính xác entry nào thiếu ID/trạng thái/trường — cứ chạy nó rồi sửa theo danh sách, không phải tự dò.

### Kiểm tra đã xong

```bash
python tools/verify.py          # phải 0 ERROR
python brain/sync/sync.py --rebuild
```

---

<!-- Version mới thêm mục ở TRÊN mục này, giữ thứ tự mới nhất trên cùng. -->
