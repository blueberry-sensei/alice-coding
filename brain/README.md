# brain — Bộ não ký ức của Alice

Lớp **trí nhớ dài hạn + retrieval** cho Alice, dựng trên engine [**ALICE CORE**](https://github.com/blueberry-sensei/alice-core) (`alicecore`, MIT). Mục tiêu: khi giao task, **tri thức liên quan được nạp đầy đủ, không sót** — kể cả liên quan *gián tiếp* qua thực thể/khái niệm chung (nhờ cơ chế event–entity + hyperedge động).

> **Mặc định BẬT.** Nếu chưa dựng được hạ tầng (Docker/model), Alice **fallback** đọc file trụ cột đầy đủ — không bao giờ kẹt. Xem [RETRIEVAL.md](RETRIEVAL.md) mục Fallback.

**Bắt đầu nhanh:** **1 lệnh** dựng cả stack (ALICE api+web + embedding `bge-m3` bundled + trang checklist) → cấu hình **LLM trong app** → chạy INITIALIZATION từ Claude/Codex desktop. Xem [SETUP.md](SETUP.md) + [stack/README.md](stack/README.md); checklist mở tại `http://localhost:8090`.

## Nguyên tắc: index dẫn xuất
- **File `knowledge/` là source-of-truth.** Não chỉ là **index dẫn xuất** để tăng recall. Mọi khẳng định vẫn phải đối chiếu source thật (`path:line#anchor`).
- **Đọc qua MCP, ghi qua Sync.** Alice **query** não bằng 8 tool MCP read-only (agent nào cũng mount MCP được → portable). **Ghi** vào não **chỉ** qua [Sync layer](SYNC.md) (REST + JWT).
- **Chỉ nuốt folder `knowledge/`** (tri thức đã tinh luyện): `wiki` + `mistakes` + `decisions` + `context` + `changelog`. **KHÔNG** index source code — code do agent đọc trực tiếp khi cần.
- **Mất não vẫn an toàn:** dựng lại 100% từ file bằng `sync.py --rebuild` (xem [SYNC.md](SYNC.md)).
- **Kho hỏng thì không cho sync.** `sync.py` chạy [`tools/verify.py`](../tools/verify.py) trước và dừng nếu có ERROR — xem [SYNC.md](SYNC.md) mục *Gate*.

## Sơ đồ

```
GHI (write)                              ĐỌC / RETRIEVE (read)
──────────                               ─────────────────────
Alice ghi/sửa trụ cột  ──►  [SYNC.py]    Task ──► [A] query não qua MCP:
  (wiki/mistakes/          map file→id     list_sources → search/grep
   context/changelog)      +sha256         → get_entity (BUNG quan hệ)
                           create/update   → get_chunk/read
                           /delete/rebuild  │
                           REST+JWT         ▼
                              │           evidence + CITATION (→ file:line)
                              ▼             │
                     ┌─── ALICE (Docker) ──┐▼
                     │ embed=bge-m3 local  │ Alice đối chiếu source thật
                     │ LLM=local|OR|AIStudio│ → "không sót"
                     │ SQLite+LanceDB       │
                     │ @ .sag-data (bind)   │ brain DOWN → fallback đọc file
                     └──────────────────────┘
```

## Ba tiêu chí khi vibe (A/B/C) — enforce PORTABLE (đa agent)
- **A — Tự nạp ký ức:** đầu task query não theo [RETRIEVAL.md](RETRIEVAL.md) đến khi đạt **tiêu chí dừng**, + in checklist *"ký ức đã nạp"* (kèm số tool call + citation) làm bằng chứng.
- **B — Sống qua auto-compact:** sau compact/thấy mơ hồ → re-query não + đọc context digest mới nhất (ALICE.md mục 9b).
- **C — Tự cải thiện:** ghi `decisions`/`mistakes` **theo từng turn**; cuối task chạy [`/knowledge`](KNOWLEDGE.md): distill → **prune** → verify → sync.

Enforce bằng **rules (ALICE.md) + vibe base-prompt + brain-qua-MCP + forcing function**. Điểm mấu chốt: A/B/C đều là chỉ dẫn *nằm trong context*, nên đều có thể bị auto-compact xoá. Lớp phòng thủ sống **ngoài** context là [`tools/verify.py`](../tools/verify.py), và nó được gắn làm **gate của `sync.py`** — chỗ nghẽn bắt buộc. Không hook, không khoá vào agent nào.

## File trong thư mục này
| File | Nội dung |
|---|---|
| [SETUP.md](SETUP.md) | Luồng 1-lệnh: dựng stack + set LLM trong app + mount MCP + chạy INITIALIZATION |
| [stack/](stack/README.md) | Docker stack 1-lệnh (ALICE api+web + embedding `bge-m3` bundled + trang checklist) + launcher |
| [RETRIEVAL.md](RETRIEVAL.md) | Giao thức query não (funnel + `get_entity` + citation + fallback + proof-of-load) |
| [SYNC.md](SYNC.md) | Đồng bộ file→não (chống trùng) + `--rebuild` |
| [KNOWLEDGE.md](KNOWLEDGE.md) | Routine `/knowledge` — tự cải thiện tri thức |
| [sync/sync.py](sync/sync.py) | Tool sync (Python, chỉ thư viện chuẩn) |
| `brain.config.example` | Khung cấu hình → copy thành `brain.config` (đã gitignore) |

## Generic
Không secret / endpoint / token / tên project trong file ship. Tất cả nằm ở `brain.config` (gitignore) hoặc slot *«điền theo máy»*. Thư mục runtime (`.sag-data/`, `.sync-state.json`, `brain.config`) đã được `.gitignore`.
