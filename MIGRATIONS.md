# MIGRATIONS — Việc phải làm tay khi lên version mới

`npm run update` tự chép file template và tự phát hiện các bước phải làm tay, rồi in ra ở cuối. File này giải thích **vì sao** và **làm thế nào** cho từng bước đó.

Quy ước version: **semver**. MAJOR đổi = có breaking change bắt buộc đọc mục tương ứng dưới đây.

---

## 2.3.7 — Dọn hai dòng nhiễu trên WSL

**Không breaking.**

- Bỏ dòng "a background process keeps the distro alive": tiến trình canh đã được thay bằng
  `vmIdleTimeout=-1`, để lại chỉ khiến người đọc tưởng còn cơ chế đó.
- `npm run brain` không còn báo "Node chưa có trong WSL" khi Node đã được cài: shell
  không-login của `wsl -e` không có `$HOME/.local/alice-node/bin` trong PATH, nay dò qua đúng PATH.

## 2.3.6 — WSL không tự tắt VM nữa

**Không breaking**, nhưng cần chạy `wsl --shutdown` MỘT lần.

- Giữ WSL bằng tiến trình canh là sai hướng: nó chết ngay khi launcher thoát, và VM vẫn tắt
  (`uptime` luôn "up 0 min") kéo theo Docker + brain.
- `npm run brain` nay thêm `vmIdleTimeout=-1` vào `%USERPROFILE%\.wslconfig` — cơ chế chính
  thức của WSL. Chỉ thêm khoá còn thiếu, không ghi đè cấu hình sẵn có.
- Sau lần đầu: `wsl --shutdown` rồi `npm run brain`.

## 2.3.5 — WSL thật sự bind 0.0.0.0

**Không breaking.** `npm run update` rồi `npm run brain`.

- 2.3.2 thêm nhánh chọn `0.0.0.0` cho WSL nhưng `brain-env.js` vẫn luôn xuất
  `BIND_ADDRESS=127.0.0.1`, nên nhánh đó **không bao giờ chạy** — container vẫn publish lên
  loopback của distro. Nay `brain-env.js` để trống nếu người dùng không khai, launcher mới quyết.

## 2.3.4 — WSL không còn tự tắt sau vài phút

**Không breaking.** `npm run update` rồi `npm run brain`.

- Tiến trình nền đặt *bên trong* distro không đủ: WSL2 vẫn tắt VM khi không còn phiên
  `wsl.exe` nào từ Windows → brain chạy được một lúc rồi chết.
- `npm run brain` nay giữ một tiến trình `wsl.exe` nền từ phía Windows. Đóng terminal vẫn OK.

## 2.3.3 — WSL in luôn URL theo IP distro

**Không breaking.** `npm run update` rồi `npm run brain`.

- WSL2 không phải máy nào cũng bật localhost-forwarding. Launcher nay in thêm
  `http://<ip-distro>:<port>` — đường luôn mở được từ Windows.

## 2.3.2 — WSL mở lại được localhost

**Không breaking.** `npm run update` rồi `npm run brain`.

- 2.3.1 đặt `BIND_ADDRESS=127.0.0.1` cho **mọi** môi trường. Trong WSL đó là loopback của
  *distro*, relay localhost của WSL2 không với tới → Windows mở `localhost:<port>` là hỏng.
  Nay WSL quay lại `0.0.0.0`; nơi khác vẫn `127.0.0.1`.
- `0.0.0.0` trong WSL **không** giống trên máy thật: WSL2 mặc định NAT nên chỉ Windows host
  chuyển tiếp vào được. Trừ khi bật *mirrored networking* — launcher có in ghi chú.

## 2.3.1 — Launcher tự cài Node trong WSL; bỏ trang checklist

**Không breaking.** Nâng cấp bằng `npm run update` rồi `npm run brain`.

- **WSL không phải cài Node tay nữa.** `npm run brain` tự tải Node vào `$HOME/.local/alice-node`
  trong distro (không cần `sudo`). Node cài bên Windows không dùng được vì Docker và launcher
  đều chạy trong distro.
- **Bỏ trang checklist** (`localhost:8090`): app đã tự hướng dẫn, một service nữa chỉ tốn cổng.
- Toàn bộ log của script chuyển sang tiếng Anh.
- `npm run uninstall -- --yes` nay dọn cả image mồ côi và build cache (thêm `--keep-cache` để giữ).

## 2.3.0 — Mỗi project một brain · kéo image thay vì clone source · secret ra khỏi repo

**Breaking với cách dựng brain.** Tri thức của bạn **không** ảnh hưởng.

### Vì sao

Ba vấn đề của bản cũ, cùng một gốc: stack bị ghim cứng vào **một** cài đặt duy nhất.

1. `compose.yaml` đặt `name: alice-brain` và cổng cố định → làm việc trên hai project cùng lúc là đụng container, đụng cổng, và **chung một kho dữ liệu**.
2. `brain/stack/.env` giữ `SAG_SECRET_KEY` **plaintext ngay trong cây repo**. Khoá đó vừa ký JWT vừa là gốc mã hoá mọi API key trong DB — lọt ra là mất hết.
3. Launcher **clone** `alice-brain` + `alice-core` rồi build tại máy → hai repo đó buộc phải public, và mỗi người dùng phải chờ build Next.js.

### Việc phải làm tay

| # | Việc | Cách làm |
|---|---|---|
| 1 | Chạy `npm run brain` một lần | Launcher tự chuyển `brain/stack/.env` ra thư mục state ngoài repo (giữ nguyên `SAG_SECRET_KEY` và mọi giá trị), rồi xoá bản trong repo. Đường dẫn mới in ra ở cuối lệnh. |
| 2 | Cắm lại MCP | Tên container nay mang `BRAIN_ID` riêng của project. Lấy khối cấu hình đúng bằng `npm run mcp`, thay cái cũ trỏ `alice-brain-api-1`. |
| 3 | Nạp lại tri thức | Dữ liệu não chuyển từ bind-mount sang named volume của Docker, **không tự di cư**. Chạy `npm run sync:rebuild`. Thư mục `brain/.sag-data/` cũ vẫn còn, xoá tay khi đã yên tâm. |
| 4 | Kiểm cổng | Cổng nay được cấp động. `npm run brain:status` in cổng thật; đừng giả định `3000`. |

### Tự động

- `BRAIN_ID` suy từ đường dẫn kho tri thức → container, network và volume của mỗi project mang tiền tố riêng. Chạy bao nhiêu project song song cũng được.
- Cổng trống được cấp lần đầu rồi giữ nguyên; project sau tự né cổng project trước đã giữ.
- Không còn clone source: launcher kéo image ALICE dựng sẵn. Máy sạch chỉ cần Docker + Node.
- `BIND_ADDRESS` luôn `127.0.0.1` (bản cũ tự mở `0.0.0.0` trên WSL — brain nói HTTP trần nên đó là đường để API key đi qua LAN ở dạng đọc được).
- Trên WSL, launcher không còn chiếm terminal; brain chạy nền, tắt bằng `npm run brain:down`.
- Lệnh mới: `npm run brain:list` (mọi brain trên máy), `npm run brain:pull` (kéo lại model embedding).
- **Bỏ trang checklist** (`localhost:8090`): app đã tự hướng dẫn, một service nữa chỉ tốn cổng.
- **WSL: Node phải cài BÊN TRONG distro.** Docker nằm ở đó nên launcher chạy ở đó; Node trên
  Windows không dùng được. `npm run brain` nay dò trước và in lệnh cài thay vì chết giữa chừng.
- `npm run uninstall -- --yes` nay dọn cả **image mồ côi** và **build cache** (bản cũ để lại vài
  chục GB sau khi "gỡ"). Có project Docker khác trên máy thì thêm `--keep-cache`.

## 2.2.0 — LLM cấu hình một chỗ trên app, nhiều provider tự chuyển nhà, log ra file

**Không breaking với tri thức của bạn.** Nhưng **credential LLM phải nhập lại một lần** trên app.

### Vì sao

Trước bản này, LLM có **hai** nơi cấu hình: biến `SAG_LLM_*` trong `brain/stack/.env` và form trên app. Hai nguồn sự thật nghĩa là một key cũ trong `.env` có thể lặng lẽ thắng cái bạn vừa nhập trên UI, và key thì nằm plaintext trong file — commit nhầm là mất key.

Từ bản này: **app là nơi duy nhất**. Ở đó khai báo được **nhiều provider theo thứ tự ưu tiên**, hệ thống tự chuyển nhà khi 429 / hết quota / sai key và ghi rõ lý do. Key được mã hoá trước khi lưu.

### Việc phải làm tay

| # | Việc | Cách làm |
|---|---|---|
| 1 | Nhập lại provider LLM | Mở `http://localhost:3000` → **Settings → Models** → thêm provider (chọn nhà, dán key, đặt model). Chưa làm thì ingest/hỏi đáp sẽ từ chối chạy và báo "chưa cấu hình LLM" — nó **không** im lặng dùng key cũ. |
| 2 | Dọn `.env` cũ | Xoá các dòng `SAG_LLM_PROVIDER` / `SAG_LLM_MODEL` / `SAG_LLM_API_KEY` / `SAG_LLM_BASE_URL` khỏi `brain/stack/.env`. Chúng không còn được đọc; để lại chỉ gây tưởng là đã cấu hình. |
| 3 | Đừng đổi `SAG_SECRET_KEY` | Khoá mã hoá credential dẫn xuất từ biến này. Đổi hoặc mất nó = mất key đã lưu, phải nhập lại (tri thức và dữ liệu não **không** ảnh hưởng). |

### Tự động

- Nhiều provider theo ưu tiên: timeout/5xx → thử lại cùng nhà; 429/hết quota → chuyển nhà và cho nhà đó nghỉ; sai key/model không tồn tại → tắt nhà đó và nêu lý do; request không hợp lệ → dừng luôn.
- Ép backend riêng của gateway (vd OpenRouter `deepinfra/fp4`) qua ô **extra body** của từng provider.
- Embedding **không** chuyển nhà (đổi model = đổi không gian vector). Nó thử lại trên cùng endpoint; hết lượt thì để document **FAILED** kèm lý do, thay vì ghi bản ghi thiếu vector rồi báo thành công như trước.
- Log ghi ra **file local**: `brain/.logs/api/sag-api.log` (API + engine, xoay vòng 20 MB × 5), `brain/.logs/brain-up.log` (dựng stack), `brain/.logs/sync.log` (sync tri thức).

### Kiểm tra đã xong

```bash
npm run doctor
```

Mục LLM phải báo đã cấu hình. Xong thì:

```bash
npm run sync
```

---

## 2.1.0 — Đổi tên repo, engine riêng, launcher tự lấy nguồn

**Không breaking với tri thức của bạn.** `update` chép file template như thường; các file instance không bị chạm.

### Vì sao

Stack cũ clone engine retrieval từ repo của bên thứ ba. Từ bản này, ALICE CODING chạy trên hai repo riêng — [`alice-core`](https://github.com/blueberry-sensei/alice-core) (engine) và [`alice-brain`](https://github.com/blueberry-sensei/alice-brain) (ứng dụng) — và repo template đổi tên thành [`alice-coding`](https://github.com/blueberry-sensei/alice-coding).

### Việc phải làm tay

| # | Việc | Cách làm |
|---|---|---|
| 1 | Dựng lại stack trên nguồn mới | `npm run uninstall -- --yes` rồi `npm run brain`. Launcher kéo image mới. **Dữ liệu não bị xoá** → phải `npm run sync:rebuild` sau đó. File tri thức là source-of-truth nên không mất gì. |
| 2 | `.env` cũ có `SAG_PATH` | Xoá dòng đó khỏi `brain/stack/.env`. Nó không còn được đọc. Muốn build từ source trên máy thì dùng `ALICE_APP_PATH` / `ALICE_CORE_PATH`. |
| 3 | Remote git trỏ tên cũ | Nếu bạn từng đặt `ALICE_TEMPLATE_REPO`, đổi sang `https://github.com/blueberry-sensei/alice-coding`. Không đặt gì thì mặc định đã đúng. |

### Tự động

- Launcher kéo image ALICE dựng sẵn từ registry; máy sạch chỉ cần Docker + Node, không cần git.
- `npm run uninstall` đã biết dọn hai thư mục clone mới.
- Ngôn ngữ prompt trích xuất nhận `en` | `vi` (bỏ `zh`).

### Kiểm tra đã xong

```bash
npm run verify
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
| 5 | Thêm `#anchor` vào citation | Mọi `` `path:line` `` trong `wiki/` đổi thành `` `path:line#tênHàm` ``. Chạy `npm run verify` để biết cái nào còn thiếu (WARN) hoặc đã trỏ sai (ERROR). |
| 6 | Sync lại não | `.sync-state.json` lên schema v2 → chạy `npm run sync:rebuild` một lần. An toàn vì file mới là source-of-truth. |

### Tự động

- `update` tạo sẵn khung rỗng cho `ALICE.project.md`, `wiki/ROUTER.md`, `decisions/` nếu chưa có.
- `sync.py` tự chặn nếu state cũ schema, kèm hướng dẫn `--rebuild`.
- `verify.py` chỉ ra chính xác entry nào thiếu ID/trạng thái/trường — cứ chạy nó rồi sửa theo danh sách, không phải tự dò.

### Kiểm tra đã xong

```bash
npm run verify          # phải 0 ERROR
npm run sync:rebuild
```

---

<!-- Version mới thêm mục ở TRÊN mục này, giữ thứ tự mới nhất trên cùng. -->
