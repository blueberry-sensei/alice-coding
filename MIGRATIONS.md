# MIGRATIONS — Việc phải làm tay khi lên version mới

`npm run update` tự chép file template và tự phát hiện các bước phải làm tay, rồi in ra ở cuối. File này giải thích **vì sao** và **làm thế nào** cho từng bước đó.

Quy ước version: **semver**. MAJOR đổi = có breaking change bắt buộc đọc mục tương ứng dưới đây.

---

## 2.4.10 — Luật ALICE tự nạp mỗi phiên và sống qua auto-compact

**Không breaking.** Sau `npm run update`, agent chạy `npm run wire` một lần.

2.4.9 chỉ sinh skill/command `alice`, nên luật chỉ có hiệu lực **khi người dùng nhớ gõ `/alice`**.
Quên gõ là phiên đó không có luật nào: agent bỏ qua nạp ký ức, quên gọi sub-agent qua Brain, ghi
tri thức xong không sync. Bản này thêm hai lớp nữa, cùng sinh từ một `prompts.md`:

- `ALICE.md` ở **root project** — base prompt đã bake, đính kèm được cho agent hoặc chat bất kỳ.
  Không còn phải chép base prompt bằng tay.
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` ở root — file mà client **tự nạp mỗi phiên**. `wire` chỉ
  thay khối giữa `<!-- BEGIN ALICE CODING -->` và `<!-- END ALICE CODING -->`; nội dung sẵn có của
  bạn giữ nguyên, chưa có file thì tạo mới.

Riêng Claude Code, `wire` merge thêm hook `SessionStart` vào
`.claude/settings.json`, chạy `node knowledge/tools/reminder.js` để in lại `ALICE.md` vào context
sau mỗi lần auto-compact. Hook chạy **ngoài** model nên compaction không xoá được — luật "sau
compact phải đọc lại" nếu chỉ nằm trong context thì chính nó cũng bị xoá. Settings có sẵn được
merge, không ghi đè; file hỏng JSON thì `wire` in `SKIP` và không đụng vào.

Project đã có `ALICE.md` riêng ở root, hoặc command/skill `alice` không mang marker ALICE → `wire`
dừng trước mọi thao tác ghi và in tên file xung đột. Đổi tên file của bạn rồi chạy lại.

Commit toàn bộ file sinh ra cùng project.

---

## 2.4.9 — Entry point ALICE cho coding agent

**Không breaking.** Sau `npm run update`, agent chạy `npm run wire` một lần nếu project đã có
`prompts.md` từ INITIALIZATION.

`wire` lấy đúng base prompt đã bake của project và sinh adapter project-local cho Claude Code,
Codex, OpenCode và Gemini CLI. Claude Code/OpenCode/Gemini dùng `/alice <task>`; Codex dùng
`$alice <task>` hoặc `/skills` vì Codex hiện không có slash `/alice` trực tiếp cho repo skill.

File adapter nên được commit cùng project. Lệnh chỉ cập nhật file có marker ALICE; nếu đã tồn tại
command/skill `alice` của người dùng, nó dừng rõ ràng và không ghi đè. `prompts.md` từ bản này
không còn bị `.gitignore` chặn, vì đó là base prompt instance của project chứ không phải file máy.

---

## 2.4.8 — Telemetry thấy lần ghi tri thức

**Không breaking.** `npm run update` rồi `npm run brain`.

Sau một lượt `npm run sync` có diff, Settings → Telemetry ghi **Knowledge write** với source,
danh sách file tạo/cập nhật/xoá và tổng `+ / ~ / -`. Event chỉ xuất hiện sau khi ingest request
thành công và `.sync-state.json` đã lưu; sửa Markdown trên host mà chưa sync không được tính là đã
ghi vào Brain. Sync không có thay đổi thì không tạo event nhiễu.

Khả năng chạy sub-agent nay tách tuyệt đối theo mode: Brain mode dùng `callable` từ
`list_sub_agents`; chỉ host-CLI mode mới phụ thuộc CLI và auth trên host. Project nâng cấp từ policy
cũ phải đánh `SUPERSEDED` mọi decision nói registry chỉ là sổ đăng ký hoặc bắt Brain slot smoke CLI.

---

## 2.4.7 — Sub-agent chạy qua Brain, không cần chép lại key

**Không breaking.** `npm run update` rồi `npm run brain`.

MCP brain có hai tool mới:

- `list_sub_agents` đọc đúng Settings → Sub Agents, chỉ trả model/trạng thái đã che credential;
- `ask_sub_agent` gọi model đã bật bằng credential được giải mã bên trong Brain, rồi tự ghi provider,
  model, token, độ trễ và kết quả xem trước lên Telemetry.

Agent không còn được đoán endpoint registry, suy registry từ CLI trên máy, hoặc bắt người dùng dán
lại key thành biến môi trường chỉ để gọi model qua Brain. Ranh giới vẫn rõ: `ask_sub_agent` chỉ nhận
task + context và không có filesystem; giao việc tự đọc/sửa file vẫn dùng host CLI với auth riêng,
sau đó khai bằng `log_agent_task`.

---

## 2.4.6 — URL và source mang danh tính project

**Không breaking.** `npm run update` rồi `npm run brain`.

Mỗi brain nay được mở bằng `http://<BRAIN_ID>.localhost:<WEB_PORT>` thay vì mọi tab đều hiện
`localhost`. `.localhost` vẫn là loopback local, không cần DNS hay sửa hosts file. Alias
`http://localhost:<WEB_PORT>` cũ vẫn hoạt động để bookmark không gãy.

Lần `npm run sync` kế tiếp đổi tên source hiện có từ `alice-knowledge` sang
`<BRAIN_ID>-knowledge` **ngay trên source cũ**; không tạo source rỗng, không ingest lại và không
tăng document count. API port/source tuỳ chỉnh trong `brain.config` vẫn được giữ nguyên.

---

## 2.4.5 — Slogan của ALICE CODING

**Không breaking.** `npm run update` là đủ.

README dùng slogan chính thức: “Một bộ não đơn giản biến Agent thành một người cộng sự tuyệt vời.”
Không có thay đổi runtime hay contract.

---

## 2.4.4 — README theo hành trình người dùng

**Không breaking.** `npm run update` là đủ.

README được viết lại theo thứ tự người mới thật sự cần: Alice Coding là gì → vấn đề của vibe
coding → cơ chế và công nghệ → cài đặt riêng cho Windows Docker Desktop, Windows WSL và macOS →
cập nhật/vận hành theo tình huống → roadmap, cảm ơn và license.

Không có thay đổi runtime hay contract. Phần benchmark nói rõ hiện chưa có bộ đo retrieval
end-to-end công khai; không dùng benchmark của riêng embedding để quảng cáo thành benchmark của
toàn sản phẩm.

---

## 2.4.3 — Telemetry: token, chi phí và dấu vết tri thức

**Không breaking.** `npm run update` rồi `npm run brain` để lấy image mới.

Brain nay ghi lại **mọi request LLM** (token vào/ra, chi phí ước tính theo bảng giá LiteLLM,
độ trễ, thành/bại) và **mọi lần agent lấy tri thức qua MCP**. Xem ở **Settings → Telemetry**.
Dữ liệu nằm trong DB của brain, không gửi đi đâu; bản ghi cũ hơn 30 ngày tự xoá
(`SAG_TELEMETRY_RETENTION_DAYS`), tắt hẳn bằng `SAG_TELEMETRY_ENABLED=false`.

Người dùng **không phải làm gì thêm** ngoài `npm run update` + `npm run brain`. Hai việc dưới đây
là của **agent**, ghi ra để agent biết:

1. Lệnh bridge MCP nay kèm `-e SAG_MCP_ACTOR=<agent>` để telemetry biết ai đang tra cứu. Agent
   tự lấy khối cấu hình bằng `npm run mcp` và tự ghi vào config của mình (INITIALIZATION Bước 5);
   việc duy nhất của người dùng là **restart agent**. Nhãn này **chỉ để hiển thị**, không cấp
   quyền gì — cấu hình cũ không có nhãn vẫn chạy, chỉ hiện tên chung `mcp-stdio`.
2. Khi delegate cho sub-agent, agent gọi tool MCP `log_agent_task` — sub-agent chạy bằng CLI
   **không** đi qua brain nên không tự hiện lên telemetry. Xem [`brain/TELEMETRY.md`](brain/TELEMETRY.md).

`INITIALIZATION.md` cũng siết lại Bước 1/3/6: quét theo bốn lượt (kiểm kê → bổ dọc từng tính
năng → quét luật/workflow/ghi chú → gom module) và **báo cáo độ phủ bằng số**.

---

## 2.4.2 — Mỗi cờ một script npm (sửa lệnh `uninstall` vô dụng trên PowerShell)

**Không breaking.** `npm run update` là đủ.

Trên **Windows PowerShell**, `npm` phân giải thành `npm.ps1`; shim đó gọi
`& $NODE_EXE $NPM_CLI_JS $args` và PowerShell **nuốt mất token `--`**. Hệ quả:
`npm run uninstall -- --yes` chỉ tới npm dưới dạng `run uninstall --yes`, npm coi `--yes`
là cờ của chính nó và **không** chuyển tiếp → script không bao giờ thấy `--yes`, nên chỉ in
lại hướng dẫn xác nhận. Lệnh gỡ trở nên bất khả thi trên shell mặc định của Windows.

Đã đo: `cmd.exe` và `npm.cmd run … -- --yes` đều truyền đúng; chỉ nhánh `npm.ps1` mất cờ.

Lệnh mới (dùng được trên mọi shell):

| Trước | Nay |
| --- | --- |
| `npm run uninstall -- --yes` | `npm run uninstall:yes` |
| `npm run uninstall -- --yes --keep-cache` | `npm run uninstall:keep-cache` |
| `npm run reset -- --yes` | `npm run reset:yes` |
| `npm run sync -- --no-verify` | `npm run sync:no-verify` |

Cờ **có giá trị** (`--ref`, `--config`) không gói thành script được — gọi `npm.cmd run update -- --ref v2.1.0`.

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
- `npm run uninstall:yes` nay dọn cả image mồ côi và build cache (`npm run uninstall:keep-cache` để giữ).

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
- `npm run uninstall:yes` nay dọn cả **image mồ côi** và **build cache** (bản cũ để lại vài
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
| 1 | Dựng lại stack trên nguồn mới | `npm run uninstall:yes` rồi `npm run brain`. Launcher kéo image mới. **Dữ liệu não bị xoá** → phải `npm run sync:rebuild` sau đó. File tri thức là source-of-truth nên không mất gì. |
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
