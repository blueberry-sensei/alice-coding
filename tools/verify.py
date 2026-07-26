#!/usr/bin/env python3
"""verify — kiểm tra sức khoẻ kho tri thức knowledge/ (forcing function, portable).

Đây là thứ DUY NHẤT trong hệ thống chạy NGOÀI context của model, nên nó là lớp
phòng thủ sống sót qua auto-compact. Mọi luật "agent phải tự giác" trong ALICE.md
đều được đối chiếu lại ở đây bằng kiểm tra máy.

Kiểm:
  C1 citation  — `path:line#anchor` trong wiki/mistakes/decisions còn trỏ đúng chỗ
                 (--fix tự sửa số dòng khi code trôi; anchor mất => ERROR)
  C2 router    — wiki/*.md <-> wiki/ROUTER.md khớp hai chiều (không mồ côi/dangling)
  C3 mistakes  — LOG.md đúng format: ID duy nhất, trạng thái hợp lệ, đủ 6 phần
  C4 decisions — LOG.md đúng format: ID duy nhất, trạng thái hợp lệ, đủ 6 trường
  C5 context   — INDEX.md <-> file digest khớp hai chiều
  C6 supersede — mọi đích SUPERSEDED -> ID có thật
  C7 phình     — cảnh báo prune khi LOG vượt ngưỡng đọc-hết-được
  C8 phủ sóng  — (tuỳ chọn) thư mục module trong code chưa có trang wiki

Exit code: 0 = không có ERROR (WARN/INFO vẫn 0) · 1 = có ERROR · 2 = sai tham số.
Chỉ dùng thư viện chuẩn. Chạy: python tools/verify.py [--fix] [--strict] [--json]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # tiếng Việt trên console Windows
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent            # .../knowledge/tools
ROOT = HERE.parent                                # .../knowledge (ghi đè bằng --root)

DEFAULTS = {
    # Gốc source code của project — mặc định là thư mục cha của knowledge/.
    "CODE_ROOT": "..",
    # Ngưỡng "còn đọc hết được" của LOG (vượt => nhắc prune, xem brain/KNOWLEDGE.md).
    "MAX_ACTIVE_MISTAKES": "60",
    "MAX_LOG_LINES": "1200",
    "MAX_CONTEXT_DIGESTS": "40",
    # Tuỳ chọn C8: thư mục con của CODE_ROOT coi là "module" (phân tách bằng dấu phẩy).
    "CODE_MODULE_DIRS": "",
}

PILLAR_DIRS = ["wiki", "mistakes", "decisions", "context", "changelog"]
CITATION_DIRS = ["wiki", "mistakes", "decisions", "changelog"]

# File tài liệu của TEMPLATE (đầy ví dụ minh hoạ) — verify chỉ soi tri thức THẬT của
# project, không soi hướng dẫn. Bỏ qua để tránh false positive.
SKIP_NAMES = {"README.md", "_TEMPLATE.md", "ROUTER.md", "INDEX.md", "LOG.md.example"}

# `path/to/file.ext` | `path/to/file.ext:120` | `path/to/file.ext:120#anchor`
CITATION_RE = re.compile(r"^([\w./@+-]+\.[A-Za-z0-9]+)(?::(\d+))?(?:#([\w.$@-]+))?$")
ENTRY_RE = re.compile(r"^##\s+([MD]-\d{4})\s+·\s+\[(\d{4}-\d{2}-\d{2})\]\s+(.+?)\s+·\s+#([\w-]+)\s*$")
STATUS_RE = re.compile(r"^-\s+\*\*Trạng thái:\*\*\s*(.+?)\s*$")
STATUS_OK = {"ACTIVE", "RESOLVED", "RETIRED"}
SUPERSEDED_RE = re.compile(r"^SUPERSEDED\s*(?:→|->)\s*([MD]-\d{4})$")

MISTAKE_FIELDS = ["Lỗi gì", "Bối cảnh", "Đã làm gì sai", "Root cause", "Bài học", "Phòng lần sau"]
DECISION_FIELDS = ["Loại", "Luật", "Vì sao", "Áp dụng khi", "Nguồn"]

FENCE_RE = re.compile(r"^\s*(```|~~~)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, check, msg, file=None, line=None):
        self.items.append({"level": level, "check": check, "msg": msg,
                           "file": file, "line": line})

    error = lambda self, *a, **k: self.add("ERROR", *a, **k)
    warn = lambda self, *a, **k: self.add("WARN", *a, **k)
    info = lambda self, *a, **k: self.add("INFO", *a, **k)

    def count(self, level):
        return sum(1 for i in self.items if i["level"] == level)


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
    for k in list(cfg):                                # env override
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def read(p):
    return p.read_text(encoding="utf-8")


def strip_noise(text):
    """Bỏ HTML comment + fenced code block: chỗ đó là ví dụ/placeholder, không phải citation thật."""
    text = COMMENT_RE.sub("", text)
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def md_files(d, skip_docs=True):
    base = ROOT / d
    if not base.exists():
        return []
    files = []
    for p in sorted(base.rglob("*.md")):
        if skip_docs and p.name in SKIP_NAMES:
            continue
        files.append(p)
    return files


# ---------------------------------------------------------------- C1 citation
def resolve(cit_path, mdfile, code_root):
    """Thử theo thứ tự: cạnh file md -> gốc knowledge/ -> gốc source code."""
    for base in (mdfile.parent, ROOT, code_root):
        cand = (base / cit_path)
        try:
            if cand.is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def check_citations(rep, cfg, do_fix):
    code_root = (ROOT / cfg["CODE_ROOT"]).resolve()
    fixed_total = 0

    for d in CITATION_DIRS:
        for md in md_files(d):
            raw = read(md)
            body = strip_noise(raw)
            rel_md = md.relative_to(ROOT).as_posix()
            replacements = {}

            for lineno, line in enumerate(body.splitlines(), 1):
                for code in INLINE_CODE_RE.findall(line):
                    m = CITATION_RE.match(code.strip())
                    if not m:
                        continue
                    cpath, cline, anchor = m.group(1), m.group(2), m.group(3)
                    if cpath.lower().endswith(".md") and cline is None:
                        target = resolve(cpath, md, code_root)
                        if target is None:
                            rep.error("C1", "link tài liệu không tồn tại: `%s`" % code,
                                      rel_md, lineno)
                        continue
                    target = resolve(cpath, md, code_root)
                    if target is None:
                        rep.error("C1", "citation trỏ file không tồn tại: `%s`" % code,
                                  rel_md, lineno)
                        continue
                    if cline is None:
                        continue

                    try:
                        src = target.read_text(encoding="utf-8", errors="replace").splitlines()
                    except OSError as e:
                        rep.warn("C1", "không đọc được %s (%s)" % (cpath, e), rel_md, lineno)
                        continue

                    n = int(cline)
                    if n < 1 or n > len(src):
                        rep.error("C1", "citation `%s` vượt số dòng file (%d dòng)"
                                  % (code, len(src)), rel_md, lineno)
                        continue
                    if not anchor:
                        rep.warn("C1", "citation `%s` thiếu #anchor -> không phát hiện được "
                                 "khi code trôi dòng (xem wiki/README.md)" % code, rel_md, lineno)
                        continue
                    if anchor in src[n - 1]:
                        continue                                  # còn đúng
                    hits = [i + 1 for i, s in enumerate(src) if anchor in s]
                    if not hits:
                        rep.error("C1", "anchor `#%s` KHÔNG còn trong %s — trang đang nói sai "
                                  "về code" % (anchor, cpath), rel_md, lineno)
                        continue
                    new = hits[0]
                    old_str = "%s:%s#%s" % (cpath, cline, anchor)
                    new_str = "%s:%d#%s" % (cpath, new, anchor)
                    if do_fix:
                        replacements[old_str] = new_str
                    else:
                        rep.warn("C1", "citation trôi dòng: `%s` -> dòng %d (chạy --fix để sửa)"
                                 % (old_str, new), rel_md, lineno)

            if do_fix and replacements:
                for old_str, new_str in replacements.items():
                    raw = raw.replace(old_str, new_str)
                md.write_text(raw, encoding="utf-8")
                fixed_total += len(replacements)
                rep.info("C1", "đã sửa %d citation trôi dòng" % len(replacements), rel_md)

    return fixed_total


# ------------------------------------------------------------------ C2 router
def check_router(rep):
    router = ROOT / "wiki" / "ROUTER.md"
    if not router.exists():
        rep.error("C2", "thiếu wiki/ROUTER.md — chưa chạy INITIALIZATION?", "wiki/ROUTER.md")
        return
    # CHỈ đọc các dòng bảng markdown (`| ... |`) — phần văn xuôi quanh bảng là hướng dẫn,
    # nhắc tên file làm ví dụ, không phải khai báo router.
    listed = set()
    for line in strip_noise(read(router)).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        for code in INLINE_CODE_RE.findall(line):
            code = code.strip()
            if code.endswith(".md"):
                listed.add(Path(code).name)
        for m in re.finditer(r"\]\(([^)]+\.md)\)", line):
            listed.add(Path(m.group(1)).name)

    skip = {"README.md", "ROUTER.md", "_TEMPLATE.md"}
    pages = {p.name for p in (ROOT / "wiki").glob("*.md")} - skip

    for orphan in sorted(pages - listed):
        rep.error("C2", "trang wiki `%s` KHÔNG có trong ROUTER.md — retrieval sẽ không "
                  "bao giờ tìm ra nó" % orphan, "wiki/ROUTER.md")
    for dangling in sorted(listed - pages):
        if (ROOT / "wiki" / dangling).exists():
            continue
        rep.error("C2", "ROUTER.md trỏ tới `%s` nhưng file không tồn tại" % dangling,
                  "wiki/ROUTER.md")
    if not pages:
        rep.info("C2", "chưa có trang wiki module nào (bản generic chưa init)", "wiki/")


# ------------------------------------------------------- C3/C4/C6 pillar LOGs
def parse_entries(path, prefix):
    """Trả về list entry dict từ một LOG.md."""
    if not path.exists():
        return []
    lines = strip_noise(read(path)).splitlines()
    entries, cur = [], None
    for i, line in enumerate(lines, 1):
        m = ENTRY_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"id": m.group(1), "date": m.group(2), "title": m.group(3),
                   "tag": m.group(4), "line": i, "status": None, "fields": set()}
            continue
        if line.startswith("## ") and cur is None:
            continue
        if cur is None:
            continue
        ms = STATUS_RE.match(line)
        if ms:
            cur["status"] = ms.group(1)
        mf = re.match(r"^-\s+\*\*(.+?):\*\*", line)
        if mf:
            cur["fields"].add(mf.group(1))
    if cur:
        entries.append(cur)
    return entries


def check_log(rep, relpath, prefix, required_fields, check_id):
    path = ROOT / relpath
    if not path.exists():
        rep.error(check_id, "thiếu %s" % relpath, relpath)
        return []
    entries = parse_entries(path, prefix)

    body = strip_noise(read(path))
    for i, line in enumerate(body.splitlines(), 1):
        if line.startswith("## ") and not ENTRY_RE.match(line):
            rep.error(check_id, "heading sai format, phải là "
                      "`## %s-0001 · [YYYY-MM-DD] tiêu đề · #tag`: %s"
                      % (prefix, line.strip()[:70]), relpath, i)

    seen = {}
    for e in entries:
        if e["id"] in seen:
            rep.error(check_id, "ID %s bị trùng (đã dùng ở dòng %d) — ID phải duy nhất "
                      "và không tái sử dụng" % (e["id"], seen[e["id"]]), relpath, e["line"])
        seen[e["id"]] = e["line"]
        if not e["id"].startswith(prefix + "-"):
            rep.error(check_id, "ID %s sai tiền tố (phải là %s-)" % (e["id"], prefix),
                      relpath, e["line"])
        if e["status"] is None:
            rep.error(check_id, "%s thiếu trường **Trạng thái**" % e["id"], relpath, e["line"])
        elif e["status"] not in STATUS_OK and not SUPERSEDED_RE.match(e["status"]):
            rep.error(check_id, "%s có trạng thái không hợp lệ: %r (hợp lệ: %s, hoặc "
                      "`SUPERSEDED → %s-XXXX`)" % (e["id"], e["status"],
                                                   " / ".join(sorted(STATUS_OK)), prefix),
                      relpath, e["line"])
        missing = [f for f in required_fields if f not in e["fields"]]
        if missing:
            rep.error(check_id, "%s thiếu trường: %s" % (e["id"], ", ".join(missing)),
                      relpath, e["line"])
    return entries


def check_supersede(rep, all_entries):
    ids = {e["id"] for e in all_entries}
    for e in all_entries:
        if not e["status"]:
            continue
        m = SUPERSEDED_RE.match(e["status"])
        if m and m.group(1) not in ids:
            rep.error("C6", "%s trỏ SUPERSEDED → %s nhưng ID đó không tồn tại"
                      % (e["id"], m.group(1)), e.get("file"), e["line"])


# ----------------------------------------------------------------- C5 context
def check_context(rep):
    cdir = ROOT / "context"
    index = cdir / "INDEX.md"
    if not index.exists():
        rep.error("C5", "thiếu context/INDEX.md", "context/INDEX.md")
        return 0
    body = strip_noise(read(index))
    listed = set()
    for m in re.finditer(r"\]\(([^)]+\.md)\)", body):
        listed.add(Path(m.group(1)).name)
    for code in INLINE_CODE_RE.findall(body):
        if code.strip().endswith(".md"):
            listed.add(Path(code.strip()).name)

    skip = {"README.md", "INDEX.md", "_TEMPLATE.md"}
    digests = {p.name for p in cdir.glob("*.md")} - skip

    for orphan in sorted(digests - listed):
        rep.error("C5", "digest `%s` không có dòng trong INDEX.md — session sau sẽ không "
                  "biết nó tồn tại" % orphan, "context/INDEX.md")
    for dangling in sorted(listed - digests):
        rep.error("C5", "INDEX.md trỏ `%s` nhưng file không tồn tại" % dangling,
                  "context/INDEX.md")
    return len(digests)


# ------------------------------------------------------------ C7 phình / prune
def check_bloat(rep, cfg, mistakes, decisions, n_digests):
    active = [e for e in mistakes if e["status"] == "ACTIVE"]
    if len(active) > int(cfg["MAX_ACTIVE_MISTAKES"]):
        rep.warn("C7", "%d mistake ACTIVE (ngưỡng %s) — tầng 2 'đọc hết ACTIVE' sắp bất khả thi. "
                 "Chạy prune/gộp theo brain/KNOWLEDGE.md"
                 % (len(active), cfg["MAX_ACTIVE_MISTAKES"]), "mistakes/LOG.md")
    for rel in ("mistakes/LOG.md", "decisions/LOG.md"):
        p = ROOT / rel
        if p.exists():
            n = len(read(p).splitlines())
            if n > int(cfg["MAX_LOG_LINES"]):
                rep.warn("C7", "%s dài %d dòng (ngưỡng %s) — cân nhắc gộp entry trùng root cause"
                         % (rel, n, cfg["MAX_LOG_LINES"]), rel)
    if n_digests > int(cfg["MAX_CONTEXT_DIGESTS"]):
        rep.warn("C7", "%d digest trong context/ (ngưỡng %s) — cân nhắc archive digest cũ"
                 % (n_digests, cfg["MAX_CONTEXT_DIGESTS"]), "context/")

    stale = [e for e in decisions if e["status"] == "ACTIVE"]
    if stale and len(stale) > 40:
        rep.info("C7", "%d decision ACTIVE — rà lại xem cái nào Bệ hạ đã đổi ý mà chưa "
                 "SUPERSEDED" % len(stale), "decisions/LOG.md")


# --------------------------------------------------------------- C8 phủ sóng
def check_coverage(rep, cfg):
    dirs = [d.strip() for d in cfg["CODE_MODULE_DIRS"].split(",") if d.strip()]
    if not dirs:
        rep.info("C8", "bỏ qua kiểm phủ sóng code→wiki (chưa đặt CODE_MODULE_DIRS trong "
                 "tools/verify.config)")
        return
    code_root = (ROOT / cfg["CODE_ROOT"]).resolve()
    wiki_text = " ".join(read(p) for p in md_files("wiki")).lower()
    for d in dirs:
        base = code_root / d
        if not base.is_dir():
            rep.warn("C8", "CODE_MODULE_DIRS trỏ `%s` nhưng không phải thư mục" % d)
            continue
        for sub in sorted(x for x in base.iterdir() if x.is_dir()):
            if sub.name.startswith((".", "_")) or sub.name in ("node_modules", "dist", "build"):
                continue
            if sub.name.lower() not in wiki_text:
                rep.info("C8", "module `%s/%s` chưa được nhắc trong wiki/ — brain không index "
                         "code, nên vùng này vô hình với retrieval" % (d, sub.name))


# --------------------------------------------------------------------- output
LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def emit(rep, as_json, fixed):
    if as_json:
        print(json.dumps({"errors": rep.count("ERROR"), "warnings": rep.count("WARN"),
                          "fixed": fixed, "items": rep.items}, ensure_ascii=False, indent=2))
        return
    print("[verify] kho tri thức: %s" % ROOT)
    if not rep.items:
        print("[verify] OK — không phát hiện vấn đề.")
        return
    for item in sorted(rep.items, key=lambda i: (LEVEL_ORDER[i["level"]], i["check"])):
        loc = ""
        if item["file"]:
            loc = " (%s%s)" % (item["file"], ":%d" % item["line"] if item["line"] else "")
        print("  [%-5s] %s %s%s" % (item["level"], item["check"], item["msg"], loc))
    print("[verify] tổng: %d ERROR · %d WARN · %d INFO%s"
          % (rep.count("ERROR"), rep.count("WARN"), rep.count("INFO"),
             " · đã tự sửa %d citation" % fixed if fixed else ""))


def main():
    ap = argparse.ArgumentParser(description="Kiểm tra sức khoẻ kho tri thức knowledge/")
    ap.add_argument("--fix", action="store_true",
                    help="tự sửa số dòng citation bị trôi (anchor còn tồn tại)")
    ap.add_argument("--strict", action="store_true", help="coi WARN như ERROR")
    ap.add_argument("--json", action="store_true", help="xuất JSON cho tool khác đọc")
    ap.add_argument("--config", default=str(HERE / "verify.config"))
    ap.add_argument("--root", default=None,
                    help="gốc kho tri thức cần kiểm (mặc định: thư mục cha của tools/)")
    args = ap.parse_args()

    if args.root:
        global ROOT
        ROOT = Path(args.root).resolve()
        if not ROOT.is_dir():
            print("[verify] --root không phải thư mục: %s" % ROOT)
            return 2

    cfg = load_config(args.config)
    rep = Report()

    fixed = check_citations(rep, cfg, args.fix)
    check_router(rep)
    mistakes = check_log(rep, "mistakes/LOG.md", "M", MISTAKE_FIELDS, "C3")
    decisions = check_log(rep, "decisions/LOG.md", "D", DECISION_FIELDS, "C4")
    for e in mistakes:
        e["file"] = "mistakes/LOG.md"
    for e in decisions:
        e["file"] = "decisions/LOG.md"
    check_supersede(rep, mistakes + decisions)
    n_digests = check_context(rep)
    check_bloat(rep, cfg, mistakes, decisions, n_digests)
    check_coverage(rep, cfg)

    emit(rep, args.json, fixed)
    bad = rep.count("ERROR") + (rep.count("WARN") if args.strict else 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
