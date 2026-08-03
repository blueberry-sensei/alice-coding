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
  C9 sub-agent — policy instance cũ không được nhập Brain mode với host CLI

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
STALE_SUB_AGENT_POLICY_MARKERS = (
    "registry là **sổ đăng ký**",
    "brain **không** chạy sub-agent hộ",
    "smoke chạy được bằng cli thật trên host",
)

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
                            rep.error("C1", "documentation link does not exist: `%s`" % code,
                                      rel_md, lineno)
                        continue
                    target = resolve(cpath, md, code_root)
                    if target is None:
                        msg = ("citation points at a missing file: `%s`"
                               " (paths must be relative to the repo root,"
                               " e.g. `brain/sync/sync.py`)" % code)
                        # If one file with that basename exists anywhere, suggest it.
                        basename = Path(cpath).name
                        candidates = []
                        for base_dir in (md.parent, ROOT, code_root):
                            try:
                                for hit in base_dir.rglob(basename):
                                    if hit.is_file():
                                        candidates.append(hit.relative_to(ROOT).as_posix())
                            except OSError:
                                continue
                        if len(candidates) == 1:
                            msg += " — did you mean `%s`?" % candidates[0]
                        elif len(candidates) > 1:
                            msg += " — found: %s" % ", ".join(sorted(candidates)[:5])
                        rep.error("C1", msg, rel_md, lineno)
                        continue
                    if cline is None:
                        continue

                    try:
                        src = target.read_text(encoding="utf-8", errors="replace").splitlines()
                    except OSError as e:
                        rep.warn("C1", "cannot read %s (%s)" % (cpath, e), rel_md, lineno)
                        continue

                    n = int(cline)
                    if n < 1 or n > len(src):
                        rep.error("C1", "citation `%s` is past the end of the file (%d lines)"
                                  % (code, len(src)), rel_md, lineno)
                        continue
                    if not anchor:
                        rep.warn("C1", "citation `%s` has no #anchor -> line drift in the code "
                                 "cannot be detected (see wiki/README.md)" % code, rel_md, lineno)
                        continue
                    if anchor in src[n - 1]:
                        continue                                  # còn đúng
                    hits = [i + 1 for i, s in enumerate(src) if anchor in s]
                    if not hits:
                        rep.error("C1", "anchor `#%s` is GONE from %s - the page now describes "
                                  "the code incorrectly" % (anchor, cpath), rel_md, lineno)
                        continue
                    new = hits[0]
                    old_str = "%s:%s#%s" % (cpath, cline, anchor)
                    new_str = "%s:%d#%s" % (cpath, new, anchor)
                    if do_fix:
                        replacements[old_str] = new_str
                    else:
                        rep.warn("C1", "citation drifted: `%s` -> line %d (run --fix to correct it)"
                                 % (old_str, new), rel_md, lineno)

            if do_fix and replacements:
                for old_str, new_str in replacements.items():
                    raw = raw.replace(old_str, new_str)
                md.write_text(raw, encoding="utf-8")
                fixed_total += len(replacements)
                rep.info("C1", "fixed %d drifted citation(s)" % len(replacements), rel_md)

    return fixed_total


# ------------------------------------------------------------------ C2 router
def check_router(rep):
    router = ROOT / "wiki" / "ROUTER.md"
    if not router.exists():
        rep.error("C2", "wiki/ROUTER.md is missing - has INITIALIZATION been run?", "wiki/ROUTER.md")
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
        rep.error("C2", "wiki page `%s` is NOT listed in ROUTER.md - retrieval will "
                  "never find it" % orphan, "wiki/ROUTER.md")
    for dangling in sorted(listed - pages):
        if (ROOT / "wiki" / dangling).exists():
            continue
        rep.error("C2", "ROUTER.md points at `%s` but that file does not exist" % dangling,
                  "wiki/ROUTER.md")
    if not pages:
        rep.info("C2", "no module wiki pages yet (generic copy, not initialised)", "wiki/")


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
                cur["text"] = "\n".join(cur.pop("lines"))
                entries.append(cur)
            cur = {"id": m.group(1), "date": m.group(2), "title": m.group(3),
                   "tag": m.group(4), "line": i, "status": None, "fields": set(),
                   "lines": [line]}
            continue
        if line.startswith("## ") and cur is None:
            continue
        if cur is None:
            continue
        cur["lines"].append(line)
        ms = STATUS_RE.match(line)
        if ms:
            cur["status"] = ms.group(1)
        mf = re.match(r"^-\s+\*\*(.+?):\*\*", line)
        if mf:
            cur["fields"].add(mf.group(1))
    if cur:
        cur["text"] = "\n".join(cur.pop("lines"))
        entries.append(cur)
    return entries


def check_log(rep, relpath, prefix, required_fields, check_id):
    path = ROOT / relpath
    if not path.exists():
        rep.error(check_id, "%s is missing" % relpath, relpath)
        return []
    entries = parse_entries(path, prefix)

    body = strip_noise(read(path))
    for i, line in enumerate(body.splitlines(), 1):
        if line.startswith("## ") and not ENTRY_RE.match(line):
            rep.error(check_id, "malformed heading, it must be "
                      "`## %s-0001 - [YYYY-MM-DD] title - #tag`: %s"
                      % (prefix, line.strip()[:70]), relpath, i)

    seen = {}
    for e in entries:
        if e["id"] in seen:
            rep.error(check_id, "duplicate ID %s (already used on line %d) - IDs must be unique "
                      "and never reused" % (e["id"], seen[e["id"]]), relpath, e["line"])
        seen[e["id"]] = e["line"]
        if not e["id"].startswith(prefix + "-"):
            rep.error(check_id, "ID %s has the wrong prefix (it must be %s-)" % (e["id"], prefix),
                      relpath, e["line"])
        if e["status"] is None:
            rep.error(check_id, "%s is missing the **Trạng thái** field" % e["id"], relpath, e["line"])
        elif e["status"] not in STATUS_OK and not SUPERSEDED_RE.match(e["status"]):
            rep.error(check_id, "%s has an invalid status: %r (valid: %s, or "
                      "`SUPERSEDED → %s-XXXX`)" % (e["id"], e["status"],
                                                   " / ".join(sorted(STATUS_OK)), prefix),
                      relpath, e["line"])
        missing = [f for f in required_fields if f not in e["fields"]]
        if missing:
            rep.error(check_id, "%s is missing field(s): %s" % (e["id"], ", ".join(missing)),
                      relpath, e["line"])
    return entries


def check_supersede(rep, all_entries):
    ids = {e["id"] for e in all_entries}
    for e in all_entries:
        if not e["status"]:
            continue
        m = SUPERSEDED_RE.match(e["status"])
        if m and m.group(1) not in ids:
            rep.error("C6", "%s is SUPERSEDED by %s but that ID does not exist"
                      % (e["id"], m.group(1)), e.get("file"), e["line"])


# ----------------------------------------------------------------- C5 context
def check_context(rep):
    cdir = ROOT / "context"
    index = cdir / "INDEX.md"
    if not index.exists():
        rep.error("C5", "context/INDEX.md is missing", "context/INDEX.md")
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
        rep.error("C5", "digest `%s` has no line in INDEX.md - later sessions will not "
                  "know it exists" % orphan, "context/INDEX.md")
    for dangling in sorted(listed - digests):
        rep.error("C5", "INDEX.md points at `%s` but that file does not exist" % dangling,
                  "context/INDEX.md")
    return len(digests)


# ------------------------------------------------------------ C7 phình / prune
def check_bloat(rep, cfg, mistakes, decisions, n_digests):
    active = [e for e in mistakes if e["status"] == "ACTIVE"]
    if len(active) > int(cfg["MAX_ACTIVE_MISTAKES"]):
        rep.warn("C7", "%d ACTIVE mistakes (threshold %s) - reading them all is becoming impractical. "
                 "Prune or merge them following brain/KNOWLEDGE.md"
                 % (len(active), cfg["MAX_ACTIVE_MISTAKES"]), "mistakes/LOG.md")
    for rel in ("mistakes/LOG.md", "decisions/LOG.md"):
        p = ROOT / rel
        if p.exists():
            n = len(read(p).splitlines())
            if n > int(cfg["MAX_LOG_LINES"]):
                rep.warn("C7", "%s is %d lines long (threshold %s) - consider merging entries sharing a root cause"
                         % (rel, n, cfg["MAX_LOG_LINES"]), rel)
    if n_digests > int(cfg["MAX_CONTEXT_DIGESTS"]):
        rep.warn("C7", "%d digests in context/ (threshold %s) - consider archiving the old ones"
                 % (n_digests, cfg["MAX_CONTEXT_DIGESTS"]), "context/")

    stale = [e for e in decisions if e["status"] == "ACTIVE"]
    if stale and len(stale) > 40:
        rep.info("C7", "%d ACTIVE decisions - review which ones have been superseded but not "
                 "SUPERSEDED" % len(stale), "decisions/LOG.md")


def check_sub_agent_policy(rep, decisions):
    """Chặn policy trước 2.4.7 đang lấy trạng thái CLI để phủ định Brain mode."""
    for entry in decisions:
        if entry["status"] != "ACTIVE":
            continue
        body = entry.get("text", "").lower()
        if any(marker in body for marker in STALE_SUB_AGENT_POLICY_MARKERS):
            rep.error(
                "C9",
                "%s conflates Brain mode with host-cli. Mark it SUPERSEDED: Brain mode uses "
                "`list_sub_agents`/`ask_sub_agent`; CLI smoke applies only to host-cli"
                % entry["id"],
                "decisions/LOG.md",
                entry["line"],
            )

    project = ROOT / "ALICE.project.md"
    if project.exists():
        body = strip_noise(read(project)).lower()
        if any(marker in body for marker in STALE_SUB_AGENT_POLICY_MARKERS):
            rep.error(
                "C9",
                "ALICE.project.md still says Brain cannot execute registered sub-agents. "
                "Update the policy: `callable=yes` governs Brain mode; host CLI has separate auth",
                "ALICE.project.md",
            )


# --------------------------------------------------------------- C8 phủ sóng
def check_coverage(rep, cfg):
    dirs = [d.strip() for d in cfg["CODE_MODULE_DIRS"].split(",") if d.strip()]
    if not dirs:
        rep.info("C8", "skipping the code-to-wiki coverage check (CODE_MODULE_DIRS is not set in "
                 "tools/verify.config)")
        return
    code_root = (ROOT / cfg["CODE_ROOT"]).resolve()
    wiki_text = " ".join(read(p) for p in md_files("wiki")).lower()
    for d in dirs:
        base = code_root / d
        if not base.is_dir():
            rep.warn("C8", "CODE_MODULE_DIRS points at `%s`, which is not a directory" % d)
            continue
        for sub in sorted(x for x in base.iterdir() if x.is_dir()):
            if sub.name.startswith((".", "_")) or sub.name in ("node_modules", "dist", "build"):
                continue
            if sub.name.lower() not in wiki_text:
                rep.info("C8", "module `%s/%s` is not mentioned in wiki/ - the brain does not index "
                         "code, nên vùng này vô hình với retrieval" % (d, sub.name))


# --------------------------------------------------------------------- output
LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}


def emit(rep, as_json, fixed):
    if as_json:
        print(json.dumps({"errors": rep.count("ERROR"), "warnings": rep.count("WARN"),
                          "fixed": fixed, "items": rep.items}, ensure_ascii=False, indent=2))
        return
    print("[verify] knowledge base: %s" % ROOT)
    if not rep.items:
        print("[verify] OK - no issues found.")
        return
    for item in sorted(rep.items, key=lambda i: (LEVEL_ORDER[i["level"]], i["check"])):
        loc = ""
        if item["file"]:
            loc = " (%s%s)" % (item["file"], ":%d" % item["line"] if item["line"] else "")
        print("  [%-5s] %s %s%s" % (item["level"], item["check"], item["msg"], loc))
    print("[verify] total: %d ERROR | %d WARN | %d INFO%s"
          % (rep.count("ERROR"), rep.count("WARN"), rep.count("INFO"),
             " · đã tự sửa %d citation" % fixed if fixed else ""))


def main():
    ap = argparse.ArgumentParser(description="Check the health of the knowledge/ base")
    ap.add_argument("--fix", action="store_true",
                    help="fix drifted citation line numbers (when the anchor still exists)")
    ap.add_argument("--strict", action="store_true", help="treat WARN as ERROR")
    ap.add_argument("--json", action="store_true", help="emit JSON for other tools to read")
    ap.add_argument("--config", default=str(HERE / "verify.config"))
    ap.add_argument("--root", default=None,
                    help="root of the knowledge base to check (default: the parent of tools/)")
    args = ap.parse_args()

    if args.root:
        global ROOT
        ROOT = Path(args.root).resolve()
        if not ROOT.is_dir():
            print("[verify] --root is not a directory: %s" % ROOT)
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
    check_sub_agent_policy(rep, decisions)
    check_coverage(rep, cfg)

    emit(rep, args.json, fixed)
    bad = rep.count("ERROR") + (rep.count("WARN") if args.strict else 0)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
