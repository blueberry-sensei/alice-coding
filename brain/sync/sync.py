#!/usr/bin/env python3
"""Brain sync — đồng bộ folder knowledge/ vào SAG mà KHÔNG tạo document trùng.

File knowledge/ là source-of-truth. Script giữ map file -> {document_id, sha256}
trong brain/.sync-state.json, rồi create/update/delete theo diff.
- update = delete document cũ + ingest lại (SAG không có upsert/idempotency).
- --rebuild = xoá sạch source rồi ingest lại toàn bộ (khi mất .sag-data / đổi embedding model).

TRƯỚC KHI SYNC, script chạy tools/verify.py và DỪNG nếu kho tri thức có ERROR — xem
run_verify(). Đây là forcing function portable của hệ thống (không cần hook riêng agent).

Chỉ dùng thư viện chuẩn. Chạy: python brain/sync/sync.py [--rebuild] [--no-verify]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
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
                    stamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

# Bump khi đổi cấu trúc .sync-state.json. State cũ hơn -> buộc --rebuild thay vì
# diễn giải sai map file->document rồi tạo document trùng.
STATE_SCHEMA = 2

DEFAULTS = {
    "SAG_API_BASE": "http://localhost:8000/api/v1",
    "SAG_AUTH_NAME": "Alice",
    "SAG_TOKEN": "",
    "BRAIN_SOURCE_NAME": "alice-knowledge",
    "BRAIN_ROOT": str(KNOWLEDGE_DIR),            # knowledge/
    "BRAIN_INCLUDE": "wiki,mistakes,decisions,context,changelog",
    "BRAIN_EXCLUDE": "_TEMPLATE.md",
    "STATE_FILE": str(BRAIN_DIR / ".sync-state.json"),
}


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
    for k in list(cfg):                          # env override
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def http(method, url, token=None, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
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
    if cfg["SAG_TOKEN"]:
        return cfg["SAG_TOKEN"]
    res = http("POST", cfg["SAG_API_BASE"] + "/auth/login", data={"name": cfg["SAG_AUTH_NAME"]})
    tok = res.get("access_token") or res.get("token")
    if not tok:
        raise SystemExit("[brain-sync] Login failed: %s" % res)
    return tok


def ensure_source(cfg, token):
    base, name = cfg["SAG_API_BASE"], cfg["BRAIN_SOURCE_NAME"]
    for s in as_items(http("GET", base + "/sources", token=token)):
        if s.get("name") == name:
            return s.get("id")
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


def load_state(cfg, rebuild):
    sp = Path(cfg["STATE_FILE"])
    if not sp.exists():
        return {"schema": STATE_SCHEMA, "source_id": None, "files": {}}
    state = json.loads(sp.read_text(encoding="utf-8"))
    found = state.get("schema", 1)
    if found != STATE_SCHEMA and not rebuild:
        raise SystemExit(
            "[brain-sync] .sync-state.json là schema v%s, script cần v%s.\n"
            "  Chạy: python brain/sync/sync.py --rebuild  (dựng lại não từ file — an toàn,\n"
            "  vì file knowledge/ mới là source-of-truth)." % (found, STATE_SCHEMA))
    state["schema"] = STATE_SCHEMA
    return state


def save_state(cfg, state):
    Path(cfg["STATE_FILE"]).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_verify(skip):
    """Gate: kho tri thức hỏng thì KHÔNG cho sync.

    Đây là forcing function của cả hệ thống. sync là chỗ nghẽn bắt buộc (không sync
    thì não không có tri thức mới -> agent mất recall), nên đặt kiểm tra ở đây khiến
    kỷ luật trở thành bắt buộc mà vẫn không cần hook riêng của agent nào.
    """
    if skip:
        print("[brain-sync] SKIPPING verify (--no-verify) - debugging only.")
        return
    script = KNOWLEDGE_DIR / "tools" / "verify.py"
    if not script.exists():
        print("[brain-sync] ! tools/verify.py not found - skipping the gate.")
        return
    proc = subprocess.run([sys.executable, str(script)], cwd=str(KNOWLEDGE_DIR))
    if proc.returncode != 0:
        raise SystemExit(
            "\n[brain-sync] DỪNG: kho tri thức đang có ERROR (xem ở trên).\n"
            "  Sync lúc này sẽ nhồi tri thức sai/mồ côi vào não và làm recall tệ đi.\n"
            "  Sửa hết ERROR rồi chạy lại. Citation trôi dòng: python tools/verify.py --fix")


def ingest(cfg, token, source_id, relpath, text):
    res = http("POST", "%s/sources/%s/documents/ingest" % (cfg["SAG_API_BASE"], source_id),
               token=token, data={"title": relpath, "text": text})
    return res.get("id") or res.get("document_id") or (res.get("document") or {}).get("id")


def delete_doc(cfg, token, source_id, doc_id):
    if not doc_id:
        return
    try:
        http("DELETE", "%s/sources/%s/documents/%s" % (cfg["SAG_API_BASE"], source_id, doc_id),
             token=token)
    except SystemExit as e:
        print("  ! ignoring delete error for %s: %s" % (doc_id, e))


def main():
    ap = argparse.ArgumentParser(description="Brain sync (SAG)")
    ap.add_argument("--config", default=str(BRAIN_DIR / "brain.config"))
    ap.add_argument("--rebuild", action="store_true",
                    help="Xoá sạch source rồi ingest lại toàn bộ từ file")
    ap.add_argument("--no-verify", action="store_true",
                    help="Bỏ qua gate tools/verify.py (KHÔNG khuyến khích)")
    args = ap.parse_args()

    run_verify(args.no_verify)

    cfg = load_config(args.config)
    token = get_token(cfg)
    source_id = ensure_source(cfg, token)
    state = load_state(cfg, args.rebuild)
    state["source_id"] = source_id
    root, files = target_files(cfg)

    def rel(p):
        return str(p.relative_to(root)).replace("\\", "/")

    if args.rebuild:
        print("[brain-sync] REBUILD: deleting every document in the source, then re-ingesting...")
        for d in as_items(http("GET", "%s/sources/%s/documents" % (cfg["SAG_API_BASE"], source_id),
                                token=token)):
            delete_doc(cfg, token, source_id, d.get("id"))
        state["files"] = {}

    seen, created, updated, deleted, skipped = set(), 0, 0, 0, 0
    for p in files:
        r = rel(p)
        seen.add(r)
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        entry = state["files"].get(r)
        if entry and entry.get("sha256") == h and not args.rebuild:
            skipped += 1
            continue
        if entry and entry.get("document_id"):        # đổi -> xoá cũ trước
            delete_doc(cfg, token, source_id, entry["document_id"])
        doc_id = ingest(cfg, token, source_id, r, p.read_text(encoding="utf-8"))
        state["files"][r] = {"document_id": doc_id, "sha256": h}
        if entry:
            updated += 1
            print("  ~ update %s" % r)
        else:
            created += 1
            print("  + ingest %s" % r)

    for r in list(state["files"]):                    # file đã xoá trên đĩa
        if r not in seen:
            delete_doc(cfg, token, source_id, state["files"][r].get("document_id"))
            del state["files"][r]
            deleted += 1
            print("  - delete %s" % r)

    save_state(cfg, state)
    print("[brain-sync] done: +%d ~%d -%d (skipped %d). source=%s (%s)"
          % (created, updated, deleted, skipped, cfg["BRAIN_SOURCE_NAME"], source_id))
    print("[brain-sync] event/entity extraction runs in the background; wait for READY before searching.")


if __name__ == "__main__":
    _install_file_log()
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        # Traceback phải nằm trong file log, không chỉ trên terminal đã đóng.
        import traceback

        traceback.print_exc()
        print("[brain-sync] FAILED - details in %s" % LOG_FILE)
        raise
