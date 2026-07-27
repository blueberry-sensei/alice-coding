<div align="center">

# 🧠 ALICE CODING

### Biến bất kỳ AI coding agent nào thành cộng sự **kỷ luật · trung thực · có trí nhớ dài hạn** — *không bao giờ quên context.*

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.3.1-6E56CF)](VERSION)
[![Engine](https://img.shields.io/badge/engine-ALICE%20CORE-6E56CF)](https://github.com/blueberry-sensei/alice-core)
[![Embedding](https://img.shields.io/badge/embedding-bge--m3%20(local)-2EA043)](https://huggingface.co/BAAI/bge-m3)
[![Runtime](https://img.shields.io/badge/runtime-Docker-2496ED?logo=docker&logoColor=white)](#-cài-đặt)
[![OS](https://img.shields.io/badge/OS-Windows%20·%20macOS%20·%20WSL-555)](#-cài-đặt)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](brain/sync/sync.py)

**[Tổng quan](#-tổng-quan)** · **[Kiến trúc](#️-kiến-trúc--công-nghệ)** · **[Cài đặt](#-cài-đặt)** · **[Dùng hằng ngày](#-dùng-hằng-ngày)** · **[Nâng cấp](#-nâng-cấp)** · **[Roadmap](#️-roadmap)**

</div>

---

## ✨ Tổng quan

AI coding agent rất mạnh, nhưng có một điểm chí mạng: **nó quên**. Hết session là mất ký ức; giữa session thì bị *auto-compact* cắt mất chi tiết; và nếu chỉ dựa vào "rule đủ mạnh + model đủ thông minh để tự nhớ đọc đúng file" thì sớm muộn cũng **sót context** → sửa lại lỗi cũ, phá contract, đi ngược quyết định đã chốt.

**ALICE CODING** giải bài toán đó bằng ba lớp:

1. **Bộ khung kỷ luật (file)** — tách *cách làm việc* (hiến pháp [`ALICE.md`](ALICE.md)) khỏi *kiến thức dự án* (6 trụ cột) khỏi *đặc tả project* ([`ALICE.project.md`](ALICE.project.md)).
2. **Bộ não retrieval ([`brain/`](brain/README.md))** — lớp index **semantic + multi-hop** dựng trên [**ALICE CORE**](https://github.com/blueberry-sensei/alice-core), kéo ra **cả tri thức liên quan *gián tiếp***.
3. **Forcing function ([`tools/verify.py`](tools/verify.py))** — lớp kiểm tra chạy **ngoài** context của model, gắn làm gate của `sync`. Đây là thứ giữ cho hai lớp trên **không degrade âm thầm** khi dùng lâu.

> 🎭 Agent tự định danh là **Alice**, xưng **Nô tài**, gọi bạn là **Bệ hạ**. Một cộng sự tận tụy, thẳng thắn, không nịnh — và không bao giờ "báo xong khi chưa xong".

### Được gì

| Năng lực | Ý nghĩa |
|---|---|
| 🧭 **Không sót context** | Retrieval multi-hop qua *event–entity*, có **tiêu chí dừng** rõ ràng thay vì "query vài lần rồi thôi". |
| 🗣️ **Nhớ ý muốn của bạn** | Trụ cột [`decisions/`](decisions/README.md) ghi sở thích/quyết định của bạn **ngay trong turn** bạn nói ra, không đợi cuối phiên. |
| 🧹 **Không thành bãi rác** | ID ổn định + trạng thái `SUPERSEDED`/`RESOLVED` + bước **prune** — tri thức được *sửa*, không chỉ *chồng thêm*. |
| 🛡️ **Kỷ luật kiểm được bằng máy** | `verify.py` bắt citation chết, trang wiki mồ côi, entry sai format; `sync` **từ chối chạy** nếu kho hỏng. |
| ⬆️ **Nâng cấp 1 lệnh** | `update.py` tách bạch template ↔ tri thức của bạn — pull bản mới không đụng một dòng nào bạn viết. |
| 🔒 **Local-first & riêng tư** | Embedding `bge-m3` chạy **local**; dữ liệu não nằm trên máy bạn (SQLite + LanceDB). |
| 🤝 **Đa agent** | Claude Code, Codex, Gemini, opencode… đều nói **MCP** → cùng một bộ não. Không hook riêng agent nào. |

---

## 🧠 Ba tiêu chí "khi vibe"

<div align="center">

| | Tiêu chí | Cơ chế | Ép bằng gì |
|:-:|---|---|---|
| **A** | **Tự động nạp ký ức** | Đầu task query não (MCP) + in *"ký ức đã nạp"* kèm số tool call & citation | proof-of-load + tiêu chí dừng |
| **B** | **Sống sót qua auto-compact** | Sau khi bị tóm tắt → tự *rehydrate* từ file + re-query não | checkpoint digest có mục "đọc lại từ đây" |
| **C** | **Tự chủ động cải thiện** | Ghi `decisions`/`mistakes` **theo turn**; cuối task distill → prune → sync | **`verify.py` làm gate của `sync.py`** |

</div>

Điểm mấu chốt: A/B/C đều là chỉ dẫn *nằm trong context* → đều có thể bị auto-compact xoá mất. Nên lớp cuối cùng phải sống **ngoài** context. Đó là `verify.py`, và nó chặn `sync` — chỗ nghẽn bắt buộc (không sync thì não không có tri thức mới). Kỷ luật thành bắt buộc mà vẫn **portable 100%**.

---

## 🏛️ Kiến trúc & Công nghệ

### Nguyên tắc: **index dẫn xuất** (file = source-of-truth)

```mermaid
flowchart LR
    subgraph SoT["📁 Nguồn sự thật — git, human-diff"]
      P["wiki · mistakes · decisions<br/>context · changelog"]
    end
    subgraph Gate["🛡️ tools/verify.py"]
      V["citation · router · format<br/>ID trùng · supersede · phình"]
    end
    subgraph Brain["🧠 Bộ não (ALICE CORE, chạy local)"]
      direction TB
      EMB["bge-m3 embedding"]
      IDX["event · entity · hyperedge động"]
      DB[("SQLite + LanceDB")]
      EMB --- IDX --- DB
    end
    Agent(["🤖 Alice — Claude / Codex / Gemini / opencode"])

    P --> Gate
    Gate -- "sạch: sync.py (chống trùng)" --> Brain
    Gate -. "hỏng: CHẶN sync" .-> P
    Agent == "① MCP: search / grep / get_entity" ==> Brain
    Brain == "② evidence + citation → path:line#anchor" ==> Agent
    Agent -. "③ ghi tri thức mới (/knowledge)" .-> P
```

- **Đọc qua MCP, ghi qua sync.** Agent chỉ *truy vấn* não (8 tool read-only). Việc *ghi* đi qua [`sync.py`](brain/sync/sync.py) — giữ map `file → document_id + sha256` nên **không bao giờ tạo document trùng**.
- **Chỉ nuốt thư mục tri thức** đã chưng cất, **không** index source code thô.
- **Kho hỏng thì không cho sync** — nhồi trang mồ côi/citation chết vào não làm recall *tệ đi*.

### Vì sao không dùng RAG thường

Dense RAG chấm điểm chunk theo độ giống vector → hay sót đúng thứ chỉ liên quan **gián tiếp**. [ALICE CORE](https://github.com/blueberry-sensei/alice-core) làm khác: mỗi chunk sinh **1 event** (một mệnh đề có nghĩa trọn vẹn) + **N entity** (điểm để mở rộng); lúc query, các event **join qua entity chung** để dựng *hyperedge động* → bung sang tri thức mà truy vấn gốc không hề nhắc tới.

Đúng thứ ta cần: hỏi "sửa hàm A" mà vẫn kéo ra được quyết định cũ về module B chỉ vì cả hai cùng chạm một entity.

### Sáu trụ cột tri thức

| Trụ cột | Trả lời câu hỏi | Cách chống phình |
|---|---|---|
| [`wiki/`](wiki/README.md) | Hệ thống **đang** ra sao? | sửa tại chỗ + tách trang |
| [`mistakes/`](mistakes/README.md) | Alice **đã sai** gì? | `RESOLVED` / `SUPERSEDED` + gộp |
| [`decisions/`](decisions/README.md) | Bệ hạ **muốn** thế nào? | `SUPERSEDED` / `RETIRED` |
| [`context/`](context/README.md) | Phiên đó **diễn ra** thế nào? | 1 phiên 1 file, archive digest cũ |
| [`changelog/`](changelog/README.md) | Code **đã đổi** gì? | append-only có chủ đích, giữ compact |
| [`sub-agents/`](sub-agents/README.md) | Khi nào **giao việc** cho agent phụ? | (không phải kho tri thức) |

### Bộ công nghệ

| Lớp | Công nghệ |
|---|---|
| Retrieval engine | **ALICE CORE** / `alicecore` (MIT, Python 3.11+) |
| Embedding (local) | **BAAI/bge-m3** phục vụ qua Ollama (OpenAI-compatible) |
| LLM (extract/rerank) | Cấu hình trong app — **AIStudio/Gemini free**, OpenRouter, hoặc local |
| Lưu trữ | SQLite + LanceDB (bind-mount, gitignore) |
| Giao tiếp agent | **MCP** (Streamable HTTP) + REST |
| Orchestration | **Docker Compose** (ALICE api+web + embedding) |
| Tooling | **Python, chỉ thư viện chuẩn** — `tools/verify.py`, `tools/update.py`, `brain/sync/sync.py` |

---

## 🚀 Cài đặt

> **TL;DR — 3 bước là có app xài.**
>
> **🪟 Windows / PowerShell:**
> ```powershell
> git clone https://github.com/blueberry-sensei/alice-coding.git knowledge; Remove-Item -Recurse -Force knowledge\.git
> ```
>
> **🍎🐧 macOS / Linux / WSL:**
> ```bash
> git clone https://github.com/blueberry-sensei/alice-coding.git knowledge && rm -rf knowledge/.git
> ```
>
> Rồi **một lệnh** cho mọi hệ (launcher tự chọn script đúng môi trường):
> ```bash
> npm run brain
> ```
> Trên **WSL**, launcher sẽ **stream log và GIỮ chạy** — **đừng đóng cửa sổ đó**. *(mac/Linux/Docker Desktop: chạy xong tự thoát.)* Không có Node? Xem [lệnh gốc](#-cài-đặt) trong mục chi tiết bên dưới.
>
> Rồi mở `http://localhost:3000` → **Settings → Models** → thêm provider LLM (key Gemini free là đủ). **Xong.**
>
> Để agent dùng não: chạy **INITIALIZATION** (Bước 4) — agent tự nạp kiến thức repo + **tự cắm MCP**, rồi bạn **restart agent**.

> ⚠️ **Xoá `knowledge/.git` sau khi clone** rồi **commit `knowledge/` vào repo project của bạn**. Tri thức là tài sản của project. Từ v2, nâng cấp template đi qua `npm run update` chứ **không** qua `git pull` — nên không cần repo lồng repo nữa.

### 🟢 Có Node? Dùng lệnh npm cho gọn

Lớp vỏ npm **không có dependency nào** — nó chỉ dò môi trường (Docker Desktop / Docker CE trong WSL / mac / Linux), tìm đúng Python, rồi gọi launcher + script Python thật. Không có Node vẫn dùng được 100% bằng lệnh gốc.

```bash
npm install
```

```bash
npm run doctor
```

```bash
npm run brain
```

```bash
npm run uninstall
```

| Lệnh | Làm gì |
|---|---|
| `npm run doctor` | Kiểm môi trường: Docker, Node, API, LLM, kho tri thức. **Chạy đầu tiên và mỗi khi thấy lạ.** |
| `npm run brain` | Dựng/khởi động brain của project này. Cũng là lệnh **kéo bản app mới** về. |
| `npm run brain:status` | Brain của project này: chế độ, cổng thật, container còn sống không |
| `npm run brain:list` | **Mọi** brain trên máy — id, cổng, cái nào đang chạy |
| `npm run brain:down` / `:restart` / `:logs` | Tắt / khởi động lại / xem log |
| `npm run brain:pull` | Kéo lại model embedding nếu lần đầu bị lỗi mạng |
| `npm run verify` / `verify:fix` | Soi sức khoẻ kho tri thức. `:fix` nắn citation trôi dòng |
| `npm run sync` / `sync:rebuild` | Đẩy `knowledge/` vào não. `:rebuild` xoá sạch rồi nạp lại |
| `npm run update:check` / `update` | Xem có bản template mới / nâng cấp template |
| `npm run mcp` | In sẵn khối cấu hình MCP đúng cho brain của project này |
| `npm run uninstall -- --yes` | Gỡ sạch Docker của brain này (container, volume, image, build cache). **Giữ** tri thức |
| `npm run reset -- --yes` | XOÁ tri thức project rồi kéo lại template trắng |

### Nâng cấp: hai lệnh, không phải một

`npm run update` chỉ chép **file template** (`knowledge/`) — nó không biết gì về Docker. Bản
**ứng dụng** nằm trong image, và image chỉ được kéo về khi dựng lại:

```bash
npm run update && npm run brain
```

Lệnh đầu cập nhật khung tri thức và in ra việc phải làm tay (nếu có); lệnh sau kéo image mới rồi
khởi động lại. Chỉ chạy `npm run update` thì khung mới nhưng app vẫn là bản cũ.

**`npm run doctor` là lệnh nên chạy đầu tiên và mỗi khi thấy lạ** — nó nói thẳng cái gì thiếu và sửa thế nào.

### Yêu cầu
- **Docker** (Docker Desktop, hoặc Docker Engine/CE trong WSL) đang chạy.
- **Node 18+** — bắt buộc: launcher dùng nó để tính danh tính brain và cấp cổng.
- **Git** và **Python 3.9+** (cho `verify` / `sync` / `update`; bạn không phải gõ lệnh Python nào).
- ~**6–8GB** trống (image app + model `bge-m3`).
- Một **API key LLM free** — khuyên [AIStudio/Gemini](https://aistudio.google.com/apikey).
- *(Tùy chọn, để chạy INITIALIZATION)* **Claude Desktop** hoặc **Codex Desktop**.

### Bước 1 — Lấy source (vào repo project của bạn)

🪟 **PowerShell:**
```powershell
git clone https://github.com/blueberry-sensei/alice-coding.git knowledge; Remove-Item -Recurse -Force knowledge\.git
```

🍎🐧 **macOS / Linux / WSL:**
```bash
git clone https://github.com/blueberry-sensei/alice-coding.git knowledge && rm -rf knowledge/.git
```

### Bước 2 — Khởi động bằng **1 lệnh**, mọi hệ điều hành như nhau

```bash
cd knowledge && npm run brain
```

Launcher tự dò môi trường (Docker Desktop / Docker Engine trong WSL / macOS / Linux), tự cấp cổng
trống, kéo image ALICE dựng sẵn về và chạy **nền**. Không cần source, không cần sửa file cấu hình,
không phải giữ cửa sổ terminal — kể cả trên WSL.

Xong, nó in ra đúng địa chỉ kèm cổng đã cấp.

> 💡 **WSL:** chạy lệnh trong terminal WSL (Docker nằm trong đó). Nên để project trong filesystem
> của WSL (`~/…`) thay vì `/mnt/d/…` cho nhanh.

### Bước 3 — Cấu hình LLM ngay trên app
Mở địa chỉ mà launcher vừa in ra (mặc định **http://localhost:3000**):
1. Mở **http://localhost:3000** → nhập tên tạo danh tính (vd `Alice`).
2. **Settings → Models** → thêm provider: key **AIStudio/Gemini** (hoặc OpenRouter). ✅ *Embedding `bge-m3` đã chạy sẵn.*
3. Tạo 1 source thử + thêm text + search → xác nhận embedding & LLM chạy.

App là **nơi duy nhất** cấu hình LLM — `.env` không còn biến `SAG_LLM_*`. Thêm được nhiều provider theo thứ tự ưu tiên: hết quota hay sai key thì hệ thống tự chuyển nhà và ghi rõ lý do trong **lịch sử gọi**. Key được mã hoá trước khi lưu nên không có gì để commit nhầm. Chi tiết: [brain/SETUP.md](brain/SETUP.md).

### Bước 4 — Chạy INITIALIZATION (agent tự làm phần còn lại)
Mở agent (Codex/Claude) trong repo project và bảo:
> *"Đọc và chạy `knowledge/INITIALIZATION.md`."*

Agent sẽ tự: **tinh luyện** repo → điền các file instance (`ALICE.project.md`, `wiki/ROUTER.md`, các trụ cột) → chạy `verify` → nạp vào não → **tự ghi config MCP `brain`** → in ra **vibe base-prompt**. Việc duy nhất của bạn sau đó: **restart agent**.

<details>
<summary>Cắm MCP thủ công (chỉ khi cần — INITIALIZATION đã tự làm)</summary>

stdio bridge — thêm vào config MCP của agent:
- **Docker CE trong WSL** + agent Windows: `command:"wsl"`, `args:["-e","docker","exec","-i","<BRAIN_ID>-api-1","python","-m","sag_api.mcp.server"]`
- **Docker Desktop / Linux / agent trong WSL:** `command:"docker"`, `args:["exec","-i","<BRAIN_ID>-api-1","python","-m","sag_api.mcp.server"]`
- Hoặc HTTP: `http://localhost:8000/mcp/` + Bearer token. Chi tiết: [`brain/SETUP.md`](brain/SETUP.md) & [`sub-agents/mcp.md`](sub-agents/mcp.md).
</details>

<details>
<summary><b>🛟 Gỡ rối nhanh</b></summary>

| Triệu chứng | Xử lý |
|---|---|
| Document **FAILED** khi extract | Chưa có provider LLM, hoặc model không phát JSON schema → thêm provider ở **Settings → Models**; xem **lịch sử gọi** để biết nhà nào fail vì gì. |
| Search rỗng / embedding lỗi | `npm run brain:logs`; embedding không tự đổi nhà (đổi model = đổi không gian vector) nên nó báo lỗi thẳng và để document FAILED. |
| `brain-up` báo `ALICE_APP_PATH sai` | Chỉ xảy ra khi bạn tự đặt biến đó. Bỏ nó đi để dùng image dựng sẵn, hoặc trỏ đúng thư mục chứa `apps/api`. |
| `sync` **dừng, báo ERROR** | Kho tri thức hỏng — đó là gate làm đúng việc. `npm run verify` xem chi tiết, `npm run verify:fix` nắn citation trôi dòng. |
| `sync` báo **sai schema state** | `npm run sync:rebuild` (an toàn, file là source-of-truth). |
| Đổi embedding model | `npm run sync:rebuild`. |
| Lỗi `\r` khi chạy `.sh` trong WSL | Đã có `.gitattributes` ép LF; nếu vẫn dính, `dos2unix` file `.sh`. |

Chi tiết vận hành: [`brain/stack/README.md`](brain/stack/README.md).
</details>

---

## 🧭 Dùng hằng ngày

Sau khi init, mỗi task chỉ cần dán **vibe base-prompt** (INITIALIZATION in ra) rồi điền việc ở `## NHIỆM VỤ`. Alice sẽ tự:

**[A]** nạp ký ức đầu task → làm theo [quy trình 5 bước](ALICE.md#4-quy-trình-5-bước-tự-hành) → **[C]** ghi `decisions`/`mistakes` **ngay trong turn** phát sinh, cuối task thì distill + prune + verify + sync; và **[B]** tự rehydrate nếu bị auto-compact.

Hai lệnh bạn nên biết:

```bash
npm run verify:fix   # kiểm & nắn kho tri thức
npm run sync         # đồng bộ file → não (tự verify trước)
```

📚 Đọc thêm: [`ALICE.md`](ALICE.md) (hiến pháp) · [`ALICE.project.md`](ALICE.project.md) (đặc tả project) · [`brain/RETRIEVAL.md`](brain/RETRIEVAL.md) (giao thức query) · [`brain/KNOWLEDGE.md`](brain/KNOWLEDGE.md) (routine tự cải thiện) · [`UPGRADE.md`](UPGRADE.md).

---

## ⬆️ Nâng cấp

```bash
npm run update
```

Một lệnh, không conflict. Ranh giới sở hữu là tuyệt đối:

| Chủ sở hữu | Gồm gì | `update` làm gì |
|---|---|---|
| **TEMPLATE** | `ALICE.md`, `INITIALIZATION.md`, `tools/`, `brain/`, `sub-agents/`, các `README`/`_TEMPLATE` | **ghi đè** (nếu bạn chưa sửa tay) |
| **INSTANCE** | `ALICE.project.md`, `wiki/ROUTER.md`, `wiki/<module>.md`, `mistakes/LOG.md`, `decisions/LOG.md`, `context/`, `changelog/`, `brain.config` | **không bao giờ chạm** |

Đã sửa tay một file template? `update` **không** ghi đè — nó để bản mới ở `<file>.new` cho bạn gộp. Chi tiết + rollback + hướng dẫn cho người bảo trì: [`UPGRADE.md`](UPGRADE.md) · [`MIGRATIONS.md`](MIGRATIONS.md).

---

## 📂 Cấu trúc repo

```
ALICE CODING/  (clone vào ./knowledge của project)
├── VERSION                ← semver của template (đường nâng cấp)
├── ALICE.md               ← [TEMPLATE] Hiến pháp: cách Alice làm việc
├── ALICE.project.md       ← [INSTANCE] Đặc tả project: stack, convention, high-risk
├── INITIALIZATION.md      ← [TEMPLATE] Bootstrap: quét repo → tinh luyện → dựng não
├── UPGRADE.md · MIGRATIONS.md   ← [TEMPLATE] Đường nâng cấp
├── tools/
│   ├── verify.py          ← forcing function: kiểm kho tri thức (gate của sync)
│   ├── update.py          ← nâng cấp template, không đụng tri thức project
│   └── manifest.json      ← ranh giới template ↔ instance (+ sha256)
├── brain/                 ← 🧠 Bộ não
│   ├── README · SETUP · RETRIEVAL · SYNC · KNOWLEDGE
│   ├── sync/sync.py       ← file→não, chống trùng, gate verify, --rebuild
│   └── stack/             ← Docker 1-lệnh: compose + launcher
├── wiki/     README(T) · ROUTER.md(I) · <module>.md(I)
├── mistakes/ README(T) · LOG.md(I)     ← ID M-XXXX + trạng thái
├── decisions/README(T) · LOG.md(I)     ← ID D-XXXX — ý muốn của Bệ hạ
├── context/  README(T) · INDEX.md(I) · <digest>.md(I)
├── changelog/README(T) · <module>.md(I)
└── sub-agents/            ← [TEMPLATE] ngưỡng delegate + thu hồi bài học
```
`(T)` = template, `update` ghi đè · `(I)` = instance, `update` không chạm.

---

## 🗺️ Roadmap

**v2.1.2** — bộ khung kỷ luật, forcing function và đường nâng cấp đã ổn định.

Đang làm:
- Wrapper `/knowledge` cho Codex · Gemini · opencode
- Benchmark `bge-m3` đối chiếu `Qwen3-Embedding`
- Bản README tiếng Anh

> Gặp lỗi khi cài? Mở issue kèm log service tương ứng — càng cụ thể càng vá nhanh.

---

## 📜 License & Credits

- Mã nguồn: [MIT](LICENSE).
- Retrieval engine: [**ALICE CORE**](https://github.com/blueberry-sensei/alice-core) (MIT).
- Ứng dụng brain: [**ALICE BRAIN**](https://github.com/blueberry-sensei/alice-brain) (MIT).
- Embedding: [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3).

<div align="center"><sub>Made with 🤍 for những phiên vibe coding không mất trí nhớ.</sub></div>

> `<BRAIN_ID>` là danh tính brain của **project này** — mỗi project một brain, nên tên khác nhau.
> Đừng gõ tay: lấy nguyên khối cấu hình bằng `npm run mcp`, và lấy cổng bằng `npm run brain:status`.
