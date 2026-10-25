#!/usr/bin/env python3
"""Brain sync — đồng bộ knowledge/ vào não theo từng ENTRY, event do chính phía ghi bóc sẵn.

Đơn vị đồng bộ là ENTRY, không phải file: mỗi `## D-xxxx`/`## M-xxxx` trong LOG, mỗi mục `##`
trong wiki/context/changelog là một document riêng. Sửa một quyết định chỉ gửi lại đúng entry
đó; 6.000 dòng còn lại không bị đụng tới.

Event của entry KHÔNG do LLM của brain bóc nữa — xem `entry_events()`:
- entry có khối `- **Sự kiện:**` → mỗi dòng con là một event agent tự viết;
- không có → suy TẤT ĐỊNH từ cấu trúc (mỗi bullet/đoạn/dòng bảng là một event).
Entity của event: ID `D-/M-xxxx`, tag `#...`, đoạn trong backtick, cộng ID/tag/đường dẫn của entry.
Brain chỉ chunk + gọi embedding (`POST .../documents/ingest-extracted`), không gọi LLM.

State brain/.sync-state.json giữ map title -> {document_id, sha256, line}. sha256 băm nội dung
entry (không băm số dòng), nên entry chỉ bị dời dòng thì chỉ cập nhật vị trí (`.../origins`).
Thay thế: ingest bản mới -> chờ READY -> source idle -> xoá đúng document cũ.

TRƯỚC KHI SYNC chạy tools/verify.py --json. Entry/file nào có ERROR thì GIỮ LẠI (báo rõ, não giữ
bản trước đó), phần sạch vẫn sync — xem verify_gate(). ERROR không gắn được vào file nào thì dừng.

Chỉ dùng thư viện chuẩn. Chạy: python brain/sync/sync.py [--rebuild] [--no-verify] [--no-wait]
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from itertools import zip_longest
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):        # tiếng Việt trên console Windows
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent          # .../knowledge/brain/sync
BRAIN_DIR = HERE.parent                          # .../knowledge/brain
KNOWLEDGE_DIR = BRAIN_DIR.parent                 # .../knowledge

# ── Log ra file ────────────────────────────────────────────────────────────
# Sync chạy một lần rồi tắt, nên output trên terminal biến mất theo cửa sổ. Ghi kèm ra file
# để khi ingest lỗi còn cái mà đọc. Tee cả stdout/stderr: không phải sửa từng print, và
# traceback (đi qua stderr) cũng vào log.
LOG_DIR = BRAIN_DIR / ".logs"
LOG_FILE = LOG_DIR / "sync.log"
LOCK_FILE = LOG_DIR / "sync.lock"
LOG_MAX_BYTES = 5 * 1024 * 1024


class _Tee:
    """Ghi song song ra console và file, mỗi dòng trong file có mốc thời gian."""

    def __init__(self, stream, handle, tag):
        self._stream = stream
        self._handle = handle
        self._tag = tag
        self._at_line_start = True

    def write(self, text):
        self._stream.write(text)
        try:
            for piece in text.splitlines(keepends=True):
                if self._at_line_start and piece.strip():
                    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    self._handle.write("%s  %s  " % (stamp, self._tag))
                self._handle.write(piece)
                self._at_line_start = piece.endswith("\n")
            self._handle.flush()
        except Exception:
            pass  # mất log còn hơn làm sync chết
        return len(text)

    def flush(self):
        self._stream.flush()
        try:
            self._handle.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self._stream, "isatty", lambda: False)()


def _install_file_log():
    """Bật tee. Lỗi mở file thì bỏ qua — log là phụ, sync vẫn phải chạy."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            LOG_FILE.replace(LOG_FILE.with_suffix(".log.1"))
        handle = LOG_FILE.open("a", encoding="utf-8")
    except OSError as error:
        print("[brain-sync] cannot write the log file (%s); console output only" % error)
        return
    sys.stdout = _Tee(sys.stdout, handle, "OUT")
    sys.stderr = _Tee(sys.stderr, handle, "ERR")


def _acquire_sync_lock():
    """Một sync tại một thời điểm: hai lượt chồng nhau sẽ ingest/xoá đè lên nhau."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handle = LOCK_FILE.open("a+b")
    if os.name == "nt":
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return handle
            except OSError:
                time.sleep(0.25)

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _release_sync_lock(handle):
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


# Bump khi đổi cấu trúc .sync-state.json. State v2 (theo file) được chuyển tự động — xem load_state().
STATE_SCHEMA = 3
# Bump khi đổi cách tách entry hoặc suy event: mọi entry sẽ được gửi lại đúng một lần.
DERIVE_VERSION = "entries-v1"

LEGACY_API_BASE = "http://localhost:8000/api/v1"
LEGACY_SOURCE_NAME = "alice-knowledge"
RUNTIME_BRAIN_ID = os.environ.get("ALICE_BRAIN_ID", "").strip()
RUNTIME_API_PORT = os.environ.get("ALICE_BRAIN_API_PORT", "").strip()

#: Tên mà bản <= 2.4.17 luôn gửi. Chỉ dùng cho brain đời cũ chưa nhận được image mới —
#: giữ nguyên tên đó để nhánh lùi không đổi hành vi so với bản người dùng đang chạy.
LEGACY_AUTH_NAME = "Alice"

DEFAULTS = {
    "SAG_API_BASE": (
        "http://localhost:%s/api/v1" % RUNTIME_API_PORT
        if RUNTIME_API_PORT else LEGACY_API_BASE
    ),
    "SAG_AUTH_NAME": "",
    "SAG_TOKEN": "",
    "BRAIN_SOURCE_NAME": (
        "%s-knowledge" % RUNTIME_BRAIN_ID
        if RUNTIME_BRAIN_ID else LEGACY_SOURCE_NAME
    ),
    "BRAIN_ROOT": str(KNOWLEDGE_DIR),            # knowledge/
    "BRAIN_INCLUDE": "wiki,mistakes,decisions,context,changelog",
    "BRAIN_EXCLUDE": "_TEMPLATE.md",
    "STATE_FILE": str(BRAIN_DIR / ".sync-state.json"),
    "BRAIN_SYNC_TIMEOUT": os.environ.get("BRAIN_SYNC_TIMEOUT", "180"),
    # Chờ tối đa bấy nhiêu giây cho chunk + vector hoá xong; lượt full đầu (~3000 entry) cần ~50 phút.
    "BRAIN_SYNC_WAIT": os.environ.get("BRAIN_SYNC_WAIT", "3600"),
}

#: Trạng thái document phía Brain (khớp `DocumentStatus` của alice-brain).
TERMINAL_OK = "ready"
TERMINAL_FAILED = "failed"
IN_PROGRESS = ("pending", "loading", "extracting")

#: Hai file LOG: entry là `## D-xxxx` / `## M-xxxx`, nhãn của event là ID + trạng thái.
LOG_FILES = ("decisions/LOG.md", "mistakes/LOG.md")


def load_config(path):
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    # Bản cũ chép ba default cứng vào brain.config. Coi đúng ba giá trị đó là default kế
    # thừa để project đang dùng tự nhận port + source identity mới; giá trị tuỳ chỉnh vẫn giữ.
    if RUNTIME_API_PORT and cfg["SAG_API_BASE"] == LEGACY_API_BASE:
        cfg["SAG_API_BASE"] = "http://localhost:%s/api/v1" % RUNTIME_API_PORT
    if RUNTIME_BRAIN_ID and cfg["BRAIN_SOURCE_NAME"] == LEGACY_SOURCE_NAME:
        cfg["BRAIN_SOURCE_NAME"] = "%s-knowledge" % RUNTIME_BRAIN_ID
    # `brain.config` là file INSTANCE — `npm run update` không bao giờ chép đè. Nên mọi project
    # đang chạy vẫn giữ dòng `SAG_AUTH_NAME=Alice` mà example đời cũ đặt sẵn, và nếu tin dòng đó
    # là lựa chọn của người dùng thì sync sẽ ĐỔI TÊN identity của họ thành "Alice" ngay lần chạy
    # đầu sau nâng cấp. Đúng giá trị mặc định cũ = không phải lựa chọn: bỏ đi để mở phiên rỗng.
    if cfg["SAG_AUTH_NAME"].strip() == LEGACY_AUTH_NAME:
        cfg["SAG_AUTH_NAME"] = ""
    for k in list(cfg):                          # env override
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


class HttpStatusError(Exception):
    """Lỗi HTTP mà chỗ gọi đã KHAI BÁO là biết cách xử lý (xem tham số `tolerate`)."""

    def __init__(self, code, detail):
        super().__init__("HTTP %s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def http(method, url, token=None, data=None, timeout=None, tolerate=()):
    if timeout is None:
        timeout = int(os.environ.get("BRAIN_SYNC_TIMEOUT", "180"))
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in tolerate:
            raise HttpStatusError(e.code, detail)
        raise SystemExit("[brain-sync] HTTP %s %s %s: %s" % (e.code, method, url, detail))
    except urllib.error.URLError as e:
        raise SystemExit("[brain-sync] Cannot reach %s (%s). Is the brain running? "
                         "Check: docker compose ps + /system/ready" % (url, e))


def as_items(res):
    if isinstance(res, list):
        return res
    for key in ("items", "data", "results", "documents", "sources"):
        if isinstance(res, dict) and isinstance(res.get(key), list):
            return res[key]
    return []


def get_token(cfg):
    """Lấy JWT: phiên cục bộ rỗng trước, brain đời cũ thì lùi về hợp đồng có tên.

    Body rỗng KHÔNG đổi tên identity đang có, còn gửi tên thì có (login cục bộ coi tên mới là
    lệnh đổi tên). Nhánh lùi tồn tại vì template và image được phát hành rời nhau.
    """
    if cfg["SAG_TOKEN"]:
        return cfg["SAG_TOKEN"]

    url = cfg["SAG_API_BASE"] + "/auth/login"
    name = cfg["SAG_AUTH_NAME"].strip()
    if name:
        res = http("POST", url, data={"name": name})
    else:
        try:
            res = http("POST", url, data={}, tolerate=(400, 422))
        except HttpStatusError:
            print("[brain-sync] This brain still requires a login name; falling back to "
                  "'%s'. Run `npm run brain` to pull the current image, which opens a local "
                  "session without one." % LEGACY_AUTH_NAME)
            res = http("POST", url, data={"name": LEGACY_AUTH_NAME})

    tok = res.get("access_token") or res.get("token")
    if not tok:
        raise SystemExit("[brain-sync] Login failed: %s" % res)
    return tok


def ensure_source(cfg, token, state):
    base, name = cfg["SAG_API_BASE"], cfg["BRAIN_SOURCE_NAME"]
    sources = as_items(http("GET", base + "/sources", token=token))
    by_id = {s.get("id"): s for s in sources if s.get("id")}
    by_name = {s.get("name"): s for s in sources if s.get("name")}

    # State source_id là danh tính mạnh hơn tên. Khi nâng cấp từ `alice-knowledge`, đổi TÊN
    # source hiện có thay vì tạo source rỗng mới; document_id và document count giữ nguyên.
    previous = by_id.get(state.get("source_id"))
    desired = by_name.get(name)
    if previous:
        if previous.get("name") == name:
            return previous.get("id")
        if desired and desired.get("id") != previous.get("id"):
            raise SystemExit(
                "[brain-sync] Cannot rename source '%s' to '%s': that name already exists."
                % (previous.get("name"), name)
            )
        updated = http(
            "PATCH",
            "%s/sources/%s" % (base, previous.get("id")),
            token=token,
            data={"name": name},
        )
        if updated.get("id") != previous.get("id"):
            raise SystemExit("[brain-sync] Could not rename the existing source: %s" % updated)
        print("[brain-sync] Renamed source: %s -> %s" % (previous.get("name"), name))
        return previous.get("id")

    if desired:
        return desired.get("id")
    created = http("POST", base + "/sources", token=token, data={"name": name})
    sid = created.get("id")
    if not sid:
        raise SystemExit("[brain-sync] Could not create the source: %s" % created)
    return sid


def target_files(cfg):
    root = Path(cfg["BRAIN_ROOT"]).resolve()
    include = [x.strip() for x in cfg["BRAIN_INCLUDE"].split(",") if x.strip()]
    exclude = [x.strip() for x in cfg["BRAIN_EXCLUDE"].split(",") if x.strip()]
    files = []
    for sub in include:
        d = root / sub
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.md")):
            if any(pat and pat in p.name for pat in exclude):
                continue
            files.append(p)
    return root, files


# ── Entry + event ───────────────────────────────────────────────────────────
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
LOG_HEADING_RE = re.compile(r"^##\s+([MD]-\d{4})\b")
STATUS_RE = re.compile(r"^-\s+\*\*Trạng thái:\*\*\s*(.+?)\s*$")
ITEM_RE = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+(.*)$")
FIELD_RE = re.compile(r"^\*\*([^*]+?):\*\*\s*(.*)$")
EVENT_BLOCK_RE = re.compile(r"^-\s+\*\*Sự kiện:\*\*\s*$")
TABLE_RE = re.compile(r"^\s*\|")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
ID_RE = re.compile(r"\b[DM]-\d{4}\b")
TAG_RE = re.compile(r"(?<![\w/#&])#([A-Za-z][\w-]*[A-Za-z0-9])")
CITATION_RE = re.compile(r"^([\w./@+-]+\.[A-Za-z0-9]+)(?::\d+)?(?:#[\w.$@-]+)?$")
WORD_RE = re.compile(r"\w")
#: Field đã nằm trong nhãn của entry (event tiêu đề mang trạng thái), không thành event riêng.
SKIP_FIELDS = {"Trạng thái"}
TITLE_MAX = 250


def plain(text):
    """Bỏ nhấn mạnh Markdown cho phần chữ của event; backtick giữ nguyên (nó mang định danh)."""
    return re.sub(r"\*\*|__", "", text).strip()


def clip(text, limit):
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    return (cut[:cut.rfind(" ")] if " " in cut[limit // 2:] else cut).rstrip() + "…"


def inline_entities(text):
    """Entity viết sẵn trong câu: đoạn backtick, ID quyết định/lỗi, tag."""
    out = []
    for span in BACKTICK_RE.findall(text):
        span = span.strip()
        cite = CITATION_RE.match(span)
        if ID_RE.fullmatch(span):
            out.append(("work", span))
        elif cite:
            out.append(("work", cite.group(1)))
        elif 2 <= len(span) <= 80:
            out.append(("technology", span))
    rest = BACKTICK_RE.sub(" ", text)
    out += [("work", value) for value in ID_RE.findall(rest)]
    out += [("concept", "#" + value) for value in TAG_RE.findall(rest)]
    return out


def make_event(line, label, crumbs, text, base_entities):
    raw = text.strip()
    body = plain(raw)
    seen, entities = set(), []
    for kind, name in list(base_entities) + inline_entities(raw):
        key = (kind, name.lower())
        if len(name.strip()) >= 2 and key not in seen:
            seen.add(key)
            entities.append({"type": kind, "name": name})
    return {
        "title": clip(body, TITLE_MAX),
        "content": " › ".join([label] + [clip(plain(c), 120) for c in crumbs] + [body]),
        "line": line,
        "entities": entities,
    }


def explicit_events(lines):
    """Khối `- **Sự kiện:**` của agent: [(dòng trong entry, câu)] hoặc None nếu entry không có."""
    for index, raw in enumerate(lines):
        if not EVENT_BLOCK_RE.match(raw):
            continue
        out = []
        for offset, sub in enumerate(lines[index + 1:], start=index + 2):
            if sub.strip() and not sub[:1].isspace():
                break
            item = ITEM_RE.match(sub)
            if item and item.group(1):
                out.append([offset, item.group(2)])
            elif sub.strip() and out:
                out[-1][1] += " " + sub.strip()
        return [(line, text) for line, text in out]
    return None


def derived_events(lines, first_line):
    """Suy event tất định: mỗi bullet, đoạn văn, dòng bảng, tiêu đề con là một mệnh đề.

    Trả về [(dòng trong entry, breadcrumb, câu)]; breadcrumb (field, bullet cha, tiêu đề con)
    đi kèm để câu đọc riêng vẫn trọn nghĩa.
    """
    out, stack, headings = [], [], []
    current, table_header, in_fence = None, None, False
    for line, raw in enumerate(lines, start=first_line):
        if FENCE_RE.match(raw):
            in_fence, current = not in_fence, None
            continue
        if in_fence:
            continue
        if not raw.strip():
            current, table_header = None, None
            continue
        heading = HEADING_RE.match(raw)
        if heading:
            level = len(heading.group(1))
            headings = [h for h in headings if h[0] < level]
            out.append([line, [h[1] for h in headings], heading.group(2)])
            headings.append((level, heading.group(2)))
            stack, current = [], None
            continue
        crumbs = [h[1] for h in headings]
        if TABLE_RE.match(raw):
            cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
            if table_header is None:
                table_header = cells
            elif not TABLE_SEP_RE.match(raw):
                pairs = zip_longest(table_header, cells, fillvalue="")
                out.append([line, crumbs, "; ".join(
                    "%s: %s" % (head, cell) if head else cell for head, cell in pairs if cell)])
            current = None
            continue
        item = ITEM_RE.match(raw)
        if item:
            indent = len(item.group(1).expandtabs(4))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parents = crumbs + [label for _, label in stack]
            field = FIELD_RE.match(item.group(2))
            if field:
                name, value = field.group(1).strip(), field.group(2)
                stack.append((indent, name))
                current = None
                if name in SKIP_FIELDS or not value.strip():
                    continue                       # field rỗng là khung cho các bullet con
                current = [line, parents + [name], value]
            else:
                current = [line, parents, item.group(2)]
                stack.append((indent, clip(plain(item.group(2)), 80)))
            out.append(current)
            continue
        if current is not None:                      # dòng nối của bullet/đoạn đang mở
            current[2] += " " + raw.strip()
            continue
        current = [line, crumbs, raw.strip()]
        out.append(current)
    return [(line, crumbs, text) for line, crumbs, text in out]


def entry_events(relpath, entry):
    """Event của một entry: tiêu đề (kèm trạng thái) + khối Sự kiện hoặc event suy từ cấu trúc."""
    lines = entry["text"].split("\n")
    heading = HEADING_RE.match(lines[0])
    log_id = LOG_HEADING_RE.match(lines[0]) if relpath in LOG_FILES else None
    status = next((m.group(1) for m in map(STATUS_RE.match, lines) if m), None)
    if log_id:
        tag = re.search(r"·\s+#([\w-]+)\s*$", lines[0])
        base = [("work", log_id.group(1))] + ([("concept", "#" + tag.group(1))] if tag else [])
        label = "%s (%s)" % (log_id.group(1), status) if status else log_id.group(1)
    else:
        base = [("work", relpath)]
        label = "%s › %s" % (relpath, heading.group(2)) if heading else relpath

    events = []
    if heading:
        title = heading.group(2) + (" — Trạng thái: %s" % status if status else "")
        events.append(make_event(1, relpath, [], title, base))
    body = lines[1:] if heading else lines
    first = 2 if heading else 1
    explicit = explicit_events(lines)
    if explicit is not None:
        found = [(line, [], text) for line, text in explicit]
    else:
        found = derived_events(body, first)
    for line, crumbs, text in found:
        if len(WORD_RE.findall(plain(text))) >= 3:
            events.append(make_event(line, label, crumbs, text, base))
    return events


def parse_entries(relpath, text):
    """Tách file thành entry theo `## ` (ngoài code fence); phần trước `##` đầu tiên là một entry."""
    lines = text.split("\n")
    starts, in_fence = [0], False
    for index, raw in enumerate(lines):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
        elif not in_fence and raw.startswith("## ") and index > 0:
            starts.append(index)
    entries, titles = [], {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        while start < end and not lines[start].strip():   # blank lines belong to no entry
            start += 1
        chunk = lines[start:end]
        while chunk and not chunk[-1].strip():
            chunk.pop()
        if not chunk:
            continue
        log_id = LOG_HEADING_RE.match(chunk[0]) if relpath in LOG_FILES else None
        if log_id:
            key = log_id.group(1)
        elif chunk[0].startswith("## "):
            key = clip(chunk[0][3:], 200)
        else:
            key = ""
        title = "%s#%s" % (relpath, key) if key else relpath
        titles[title] = titles.get(title, 0) + 1
        if titles[title] > 1:                         # tiêu đề trùng trong cùng file
            title = "%s~%d" % (title, titles[title])
        body = "\n".join(chunk)
        entry = {
            "title": title,
            "path": relpath,
            "line": start + 1,
            "end_line": start + len(chunk),
            "text": body,
            "sha256": hashlib.sha256(("%s\n%s" % (DERIVE_VERSION, body)).encode("utf-8")).hexdigest(),
        }
        entry["events"] = entry_events(relpath, entry)
        if entry["events"]:
            entries.append(entry)
    return entries


# ── State ───────────────────────────────────────────────────────────────────
def load_state(cfg):
    sp = Path(cfg["STATE_FILE"])
    if not sp.exists():
        return {"schema": STATE_SCHEMA, "source_id": None, "entries": {}, "retire": []}
    state = json.loads(sp.read_text(encoding="utf-8"))
    found = state.get("schema", 1)
    if found == 2:
        # v2 theo dõi nguyên file. Document theo file KHÔNG bị xoá trước: chúng vẫn trả lời search
        # cho tới khi mọi entry mới READY, rồi mới bị xoá ở cuối lượt — não không có lúc rỗng.
        retire = [e.get("document_id") for e in state.get("files", {}).values() if e.get("document_id")]
        print("[brain-sync] state v2 -> v3: %d file document(s) will be replaced by entries" % len(retire))
        return {"schema": STATE_SCHEMA, "source_id": state.get("source_id"), "entries": {}, "retire": retire}
    if found != STATE_SCHEMA:
        raise SystemExit(
            "[brain-sync] .sync-state.json là schema v%s, script cần v%s. Chạy `npm run sync:rebuild`\n"
            "  (dựng lại não từ file — an toàn, vì file knowledge/ mới là source-of-truth)."
            % (found, STATE_SCHEMA))
    state.setdefault("retire", [])
    return state


def save_state(cfg, state):
    Path(cfg["STATE_FILE"]).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Verify gate ─────────────────────────────────────────────────────────────
def verify_gate(skip, entries, synced_paths):
    """Gate: entry/file có ERROR thì giữ lại, phần sạch vẫn được sync.

    Trả về ({title: [lý do]} của entry bị giữ, các file bị giữ nguyên cả file). Không nới luật
    verify: `npm run verify` vẫn đỏ cho tới khi sửa xong, chỉ là một citation mồ côi ở chỗ này
    không còn chặn tri thức ở chỗ khác. ERROR không gắn được vào file nào thì không biết phần nào
    sạch -> dừng cả lượt.
    """
    if skip:
        print("[brain-sync] SKIPPING verify (--no-verify) - debugging only.")
        return {}, set()
    script = KNOWLEDGE_DIR / "tools" / "verify.py"
    if not script.exists():
        raise SystemExit("[brain-sync] tools/verify.py not found - refusing to sync unverified knowledge.")
    proc = subprocess.run([sys.executable, str(script), "--json"], cwd=str(KNOWLEDGE_DIR),
                          capture_output=True, text=True, encoding="utf-8")
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("[brain-sync] tools/verify.py did not return a JSON report (exit %s)."
                         % proc.returncode)
    errors = [item for item in report.get("items", []) if item.get("level") == "ERROR"]
    unplaced = [item for item in errors if not item.get("file")]
    if unplaced:
        for item in unplaced:
            print("  [ERROR] %s %s" % (item.get("check"), item.get("msg")))
        raise SystemExit("[brain-sync] DỪNG: verify có ERROR không gắn với file nào, nên không biết "
                         "phần nào sạch để sync. Sửa rồi chạy lại.")

    by_path = {}
    for entry in entries:
        by_path.setdefault(entry["path"], []).append(entry)
    held, held_files = {}, set()
    for item in errors:
        path, line = item["file"], item.get("line")
        where = "%s%s" % (path, ":%d" % line if line else "")
        reason = "%s %s (%s)" % (item.get("check"), item.get("msg"), where)
        if path not in synced_paths:
            print("  [ERROR outside the brain scope, blocks nothing] %s" % reason)
            continue
        hit = [e for e in by_path.get(path, []) if line and e["line"] <= line <= e["end_line"]]
        if not hit:                                  # lỗi của cả file, hoặc nằm ngoài mọi entry
            held_files.add(path)
            hit = by_path.get(path, [])
        for entry in hit:
            held.setdefault(entry["title"], []).append(reason)
    return held, held_files


# ── Brain calls ─────────────────────────────────────────────────────────────
def ingest_entry(cfg, token, source_id, entry):
    try:
        res = http(
            "POST",
            "%s/sources/%s/documents/ingest-extracted" % (cfg["SAG_API_BASE"], source_id),
            token=token,
            data={
                "title": entry["title"],
                "text": entry["text"],
                "origin_path": entry["path"],
                "origin_line": entry["line"],
                "events": entry["events"],
            },
            tolerate=(404, 405),
        )
    except HttpStatusError as error:
        raise SystemExit(
            "[brain-sync] This brain does not accept pre-extracted entries (HTTP %s): its image is "
            "older than this template. Run `npm run brain` to pull the current image, then sync again."
            % error.code)
    doc_id = res.get("id")
    if not doc_id:
        raise SystemExit("[brain-sync] Ingest returned no document id for %s: %s" % (entry["title"], res))
    return doc_id


def move_origins(cfg, token, source_id, moves):
    for start in range(0, len(moves), 500):
        http("POST", "%s/sources/%s/documents/origins" % (cfg["SAG_API_BASE"], source_id),
             token=token, data={"items": moves[start:start + 500]})


def delete_doc(cfg, token, source_id, doc_id):
    try:
        http("DELETE", "%s/sources/%s/documents/%s" % (cfg["SAG_API_BASE"], source_id, doc_id),
             token=token, tolerate=(404,))
    except HttpStatusError:
        pass  # một lượt trước đã xoá xong; mọi lỗi khác là fatal (để lại bản trùng là mất kiểm soát)


def fetch_documents(cfg, token, source_id):
    """Map document_id -> document, đọc từ Brain."""
    docs = as_items(http("GET", "%s/sources/%s/documents" % (cfg["SAG_API_BASE"], source_id),
                         token=token))
    return {d.get("id"): d for d in docs if d.get("id")}


def await_documents(cfg, token, source_id, doc_ids, wait_seconds):
    """Chờ các document vừa gửi tới trạng thái cuối; trả về (failed, pending).

    `ingest` chỉ ĐĂNG KÝ document; chunk + vector hoá chạy nền. Không chờ thì embedding hỏng vẫn
    ra "done" trong khi search không bao giờ thấy tri thức đó.
    """
    wanted = set(doc_ids)
    deadline = time.time() + wait_seconds
    announced = False
    while True:
        by_id = fetch_documents(cfg, token, source_id)
        failed, pending = [], []
        for doc_id in wanted:
            doc = by_id.get(doc_id)
            if doc is None:
                failed.append({"id": doc_id, "title": "?", "error": "document is gone from the brain"})
                continue
            status = str(doc.get("status") or "").lower()
            if status == TERMINAL_FAILED:
                failed.append({"id": doc_id, "title": doc.get("filename") or doc_id,
                               "error": doc.get("error") or "no reason reported"})
            elif status in IN_PROGRESS:
                pending.append(doc_id)
        if not pending or time.time() >= deadline:
            return failed, pending
        if not announced:
            print("[brain-sync] waiting for the brain to chunk + embed %d document(s) (up to %ds)..."
                  % (len(pending), wait_seconds))
            announced = True
        time.sleep(2)


def wait_source_idle(cfg, token, source_id, wait_seconds):
    """Không xoá khi source còn document đang ghi vector store: lệnh xoá sẽ treo rồi bỏ lại bản trùng."""
    deadline = time.time() + wait_seconds
    while True:
        busy = [d for d in fetch_documents(cfg, token, source_id).values()
                if str(d.get("status") or "").lower() in IN_PROGRESS]
        if not busy:
            return
        if time.time() >= deadline:
            raise SystemExit("[brain-sync] the source is still processing %d document(s) after %ds; "
                             "nothing was deleted. Run sync again later." % (len(busy), wait_seconds))
        time.sleep(2)


def report_knowledge_sync(cfg, token, source_id, *, created, updated, deleted, skipped, rebuild):
    """Ghi diff sau khi state đã lưu; telemetry lỗi không được làm ingest chạy lại."""
    if not created and not updated and not deleted:
        return
    try:
        result = http(
            "POST",
            cfg["SAG_API_BASE"] + "/telemetry/knowledge-sync",
            token=token,
            data={
                "actor": os.environ.get("ALICE_AGENT_ACTOR", "alice-sync"),
                "source_id": source_id,
                "source_name": cfg["BRAIN_SOURCE_NAME"],
                "created": created,
                "updated": updated,
                "deleted": deleted,
                "skipped": skipped,
                "rebuild": rebuild,
            },
        )
        if result.get("recorded") is not True:
            print("[brain-sync] WARNING: Brain accepted the sync but did not record telemetry.")
    except SystemExit as error:
        print("[brain-sync] WARNING: knowledge was synced, but telemetry was not recorded: %s" % error)


def main():
    ap = argparse.ArgumentParser(description="Brain sync (SAG), entry by entry")
    ap.add_argument("--config", default=str(BRAIN_DIR / "brain.config"))
    ap.add_argument("--rebuild", action="store_true",
                    help="Gửi lại mọi entry rồi xoá mọi document cũ của source (không có lúc não rỗng)")
    ap.add_argument("--no-verify", action="store_true",
                    help="Bỏ qua gate tools/verify.py (KHÔNG khuyến khích)")
    ap.add_argument("--no-wait", action="store_true",
                    help="Không chờ Brain vector hoá xong; sẽ KHÔNG phát hiện được document hỏng và không xoá bản cũ")
    args = ap.parse_args()

    cfg = load_config(args.config)
    root, files = target_files(cfg)
    entries = []
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        entries += parse_entries(rel, p.read_text(encoding="utf-8"))
    synced_paths = {str(p.relative_to(root)).replace("\\", "/") for p in files}
    held, held_files = verify_gate(args.no_verify, entries, synced_paths)

    state = load_state(cfg)
    token = get_token(cfg)
    source_id = ensure_source(cfg, token, state)
    state["source_id"] = source_id
    existing = fetch_documents(cfg, token, source_id)

    if args.rebuild:
        print("[brain-sync] REBUILD: every entry is sent again; old documents go only once all are READY.")
        state["retire"] = sorted(set(state["retire"]) | set(existing))
        state["entries"] = {}

    tracked_ids = {e["document_id"] for e in state["entries"].values()}
    untracked = [doc_id for doc_id in existing if doc_id not in tracked_ids and doc_id not in state["retire"]]
    if untracked:
        print("  ! %d document(s) in the source are not tracked by state; not deleting them automatically "
              "(npm run sync:rebuild replaces everything)" % len(untracked))

    seen, created, updated, moved, kept = set(), [], [], [], []
    new_ids, skipped = [], 0
    for entry in entries:
        title = entry["title"]
        seen.add(title)
        current = state["entries"].get(title)
        if title in held:
            kept.append(title)
            continue
        if current and current["sha256"] == entry["sha256"]:
            doc = existing.get(current["document_id"])
            if doc is not None and str(doc.get("status") or "").lower() != TERMINAL_FAILED:
                if current.get("line") != entry["line"]:
                    moved.append((title, {"document_id": current["document_id"], "origin_line": entry["line"]}))
                else:
                    skipped += 1
                continue
            print("  ! re-ingesting %s (the brain has it as %s)" % (title, "failed" if doc else "missing"))
        doc_id = ingest_entry(cfg, token, source_id, entry)
        if current:
            state["retire"].append(current["document_id"])
            updated.append(title)
        else:
            created.append(title)
        state["entries"][title] = {"document_id": doc_id, "sha256": entry["sha256"], "line": entry["line"]}
        new_ids.append(doc_id)
        save_state(cfg, state)                       # crash giữa chừng không mất tiến độ

    if moved:
        move_origins(cfg, token, source_id, [move for _, move in moved])
        for title, move in moved:                    # chỉ ghi vị trí mới khi brain đã nhận
            state["entries"][title]["line"] = move["origin_line"]
    deleted = []
    for title in list(state["entries"]):
        # Entry biến mất khỏi file. Cả file đang bị giữ vì ERROR thì chưa kết luận được là mất thật.
        if title not in seen and title.split("#", 1)[0] not in held_files:
            state["retire"].append(state["entries"].pop(title)["document_id"])
            deleted.append(title)
    save_state(cfg, state)

    for title in kept:
        print("  = HELD %s - verify ERROR, the brain keeps its previous copy:" % title)
        for reason in held[title]:
            print("      %s" % reason)
    print("[brain-sync] sent: +%d ~%d -%d, moved %d, unchanged %d, held back %d."
          % (len(created), len(updated), len(deleted), len(moved), skipped, len(kept)))

    if args.no_wait:
        print("[brain-sync] --no-wait: NOT checking that the brain embedded anything; old copies are kept.")
        return 0

    try:
        wait_seconds = int(cfg["BRAIN_SYNC_WAIT"])
    except (TypeError, ValueError):
        wait_seconds = 3600
    tracked = [e["document_id"] for e in state["entries"].values()]
    failed, pending = await_documents(cfg, token, source_id, tracked, wait_seconds)
    for item in failed:
        print("  ! FAILED %s: %s" % (item["title"], item["error"]))
    if failed or pending:
        # Không xoá gì: bản cũ vẫn là thứ duy nhất search thấy cho tới khi bản mới READY.
        print("\n[brain-sync] FAILED: %d failed, %d still processing after %ds (of %d tracked); "
              "old copies were kept." % (len(failed), len(pending), wait_seconds, len(tracked)))
        print("[brain-sync] Embedding errors -> npm run embedding, then npm run brain:logs. "
              "Fix the cause, then run sync again.")
        return 1

    retire = [doc_id for doc_id in dict.fromkeys(state["retire"]) if doc_id not in tracked]
    if retire:
        wait_source_idle(cfg, token, source_id, wait_seconds)
        for doc_id in retire:
            delete_doc(cfg, token, source_id, doc_id)
            state["retire"].remove(doc_id)
            save_state(cfg, state)
    state["retire"] = []
    save_state(cfg, state)

    report_knowledge_sync(cfg, token, source_id, created=created, updated=updated, deleted=deleted,
                          skipped=skipped, rebuild=args.rebuild)
    print("[brain-sync] done: +%d ~%d -%d moved %d (unchanged %d, held back %d, old copies removed %d). "
          "source=%s (%s)" % (len(created), len(updated), len(deleted), len(moved), skipped, len(kept),
                               len(retire), cfg["BRAIN_SOURCE_NAME"], source_id))
    return 0


def run_locked_sync():
    handle = _acquire_sync_lock()
    try:
        _install_file_log()
        try:
            return main() or 0
        except SystemExit:
            raise
        except BaseException:
            # Traceback phải nằm trong file log, không chỉ trên terminal đã đóng.
            import traceback

            traceback.print_exc()
            print("[brain-sync] FAILED - details in %s" % LOG_FILE)
            raise
    finally:
        _release_sync_lock(handle)


if __name__ == "__main__":
    sys.exit(run_locked_sync())
