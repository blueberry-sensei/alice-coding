# UPGRADE — Nâng cấp template mà không mất tri thức project

```bash
npm run update
```

Một lệnh. Không `git pull`, không conflict, không đụng tới tri thức bạn đã tích luỹ.

## Vì sao không dùng `git pull`

Bản v1 hướng dẫn `git clone … knowledge`, rồi INITIALIZATION **ghi thẳng vào file của template** (phụ lục `ALICE.md`, bảng router trong `wiki/README.md`, slot trong `base-prompt.md`). Hệ quả: template và dữ liệu project nằm chung file → `git pull` **chắc chắn conflict đúng vào những file bạn đã customize**, mỗi lần, vĩnh viễn. Cộng thêm repo-lồng-repo (`knowledge/` là git repo nằm trong git repo project của bạn).

Từ v2, ranh giới sở hữu là tuyệt đối:

| Chủ sở hữu | Gồm những gì | `update` làm gì |
|---|---|---|
| **TEMPLATE** | `ALICE.md`, `INITIALIZATION.md`, `README.md`, `tools/*.py`, `tools/*.js`, `brain/**`, `sub-agents/*.md`, các `README.md`/`_TEMPLATE.md` của trụ cột | **Ghi đè** (nếu bạn chưa sửa tay) |
| **INSTANCE** | `ALICE.project.md`, `wiki/ROUTER.md`, `wiki/<module>.md`, `mistakes/LOG.md`, `decisions/LOG.md`, `context/**`, `changelog/<module>.md`, `brain/brain.config`, `tools/verify.config`, `prompts.md` | **Không bao giờ chạm** |

Ranh giới này khai báo trong `tools/manifest.json` (kèm sha256 lúc phát hành), nên `update` phân biệt được **"file template bạn chưa từng động vào"** (ghi đè an toàn) với **"file template bạn đã sửa tay"** (không ghi đè — để lại `<file>.new` cho bạn tự gộp).

`update` **tự tải template về thư mục tạm** rồi áp theo manifest, nên `knowledge/` không cần là git repo của template nữa. Nó chỉ là thư mục thường trong repo project của bạn — **nên commit vào repo project** (tri thức là tài sản của project), trừ các file runtime đã có trong `.gitignore`.

## Quy trình

```bash
npm run update:check   # có bản mới không?
npm run update:dry     # sẽ đổi những gì?
npm run update         # làm thật
npm run verify         # bắt buộc: kiểm lại kho tri thức
```

Ghim một version cụ thể: `npm.cmd run update -- --ref v2.1.0` (dùng `npm.cmd`: trên PowerShell, `npm.ps1` nuốt mất `--`). Dùng fork riêng: đặt biến môi trường `ALICE_TEMPLATE_REPO`.

## Sau khi update

1. Đọc phần **MIGRATION phải làm tay** mà `update` in ra (nếu có) → đối chiếu [`MIGRATIONS.md`](MIGRATIONS.md).
2. Xử lý file `.new` nếu có xung đột: so sánh, gộp, rồi xoá `.new`.
3. Chạy `npm run verify` — nếu template siết thêm quy ước mới, đây là chỗ nó báo.
4. Nếu có ERROR về format trụ cột (vd template thêm trường bắt buộc) → sửa rồi mới `sync`. Bản thân `sync.py` cũng chặn nếu còn ERROR.
5. Chạy `npm run sync` để não khớp lại file.
6. Chạy `npm run wire` để entry point ở **root project** (`ALICE.md`, khối ALICE trong `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`, skill `/alice`) khớp lại template mới. Những file này nằm ngoài `knowledge/` nên `update` **không bao giờ** đụng tới — chỉ `wire` mới sinh lại chúng.

## Rollback

Tri thức project không bị `update` đụng nên rollback chỉ là chuyện của template: `git checkout` lại thư mục `knowledge/` trong repo project của bạn (đây là lý do nên commit `knowledge/`), hoặc `npm.cmd run update -- --ref <version-cũ>`.

## Dành cho người bảo trì template

Trước khi phát hành:

```bash
# 1. sửa VERSION theo semver
# 2. ghi mục mới vào MIGRATIONS.md nếu có breaking change
npm run manifest       # 3. sinh lại manifest
npm run verify         # 4. template phải sạch
```

`--gen-manifest` quét theo `TEMPLATE_GLOBS` trong [`tools/update.py`](tools/update.py). **Thêm file template mới thì phải thêm glob**, nếu không `update` sẽ không phát nó tới người dùng.
