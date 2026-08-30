#!/usr/bin/env python3
"""Brain sync — đồng bộ folder knowledge/ vào SAG mà KHÔNG tạo document trùng.

File knowledge/ là source-of-truth. Script giữ map file -> {document_id, sha256}
trong brain/.sync-state.json, rồi create/update/delete theo diff.
- update = delete document cũ + ingest lại (SAG không có upsert/idempotency).
- --rebuild = xoá sạch source rồi ingest lại toàn bộ (khi mất .sag-data / đổi embedding model).

TRƯỚC KHI SYNC, script chạy tools/verify.py và DỪNG nếu kho tri thức có ERROR — xem
run_verify(). Đây là forcing function portable của hệ thống (không cần hook riêng agent).

SAU KHI SYNC, script CHỜ Brain xử lý xong rồi mới kết luận — xem await_documents(). Document
nào FAILED thì sync **exit 1**. Ingest trả về ngay, còn vector hoá chạy nền, nên nếu chỉ nhìn
lượt ingest thì embedding hỏng vẫn cho ra "done" và exit 0 trong khi não không có vector nào.

Chỉ dùng thư viện chuẩn. Chạy: python brain/sync/sync.py [--rebuild] [--no-verify] [--no-wait]
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
    # Chờ tối đa bấy nhiêu giây cho extraction/vector hoá xong trước khi kết luận. Ingest trả về
    # ngay, việc thật chạy nền — không chờ thì sync không bao giờ biết tri thức có vào được não
    # hay không, và đó chính là chỗ "exit 0 nhưng não rỗng".
    "BRAIN_SYNC_WAIT": os.environ.get("BRAIN_SYNC_WAIT", "900"),
}

#: Trạng thái document phía Brain (khớp `DocumentStatus` của alice-brain).
TERMINAL_OK = "ready"
TERMINAL_FAILED = "failed"
IN_PROGRESS = ("pending", "loading", "extracting")


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
    # Ai thật sự muốn tên đó cũng ra kết quả y hệt — phiên rỗng trả về đúng identity đang có.
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

    Một brain là một người dùng trên máy của chính họ, nên body rỗng là đủ — và quan trọng hơn,
    body rỗng KHÔNG đổi tên identity đang có, còn gửi tên thì có (login cục bộ coi tên mới là
    lệnh đổi tên).

    Nhánh lùi tồn tại vì template và image được phát hành rời nhau: `npm run update` lấy template
    từ git ngay lập tức, còn image `alice-brain` phải đợi CI build xong. Trong khoảng đó, brain
    đang chạy vẫn bắt buộc có `name` và trả 422 cho body rỗng. Không có nhánh này thì `npm run
    sync` chết cho tới khi người dùng kéo được image mới.
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


def report_knowledge_sync(
    cfg,
    token,
    source_id,
    *,
    created,
    updated,
    deleted,
    skipped,
    rebuild,
):
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
        print(
            "[brain-sync] WARNING: knowledge was synced, but telemetry was not recorded: %s"
            % error
        )


def fetch_documents(cfg, token, source_id):
    """Map document_id -> document, đọc từ Brain."""
    docs = as_items(http("GET", "%s/sources/%s/documents" % (cfg["SAG_API_BASE"], source_id),
                         token=token))
    return {d.get("id"): d for d in docs if d.get("id")}


def await_documents(cfg, token, source_id, doc_ids, wait_seconds):
    """Chờ Brain xử lý xong các document vừa gửi rồi trả về (failed, pending).

    Vì sao phải chờ: `POST /documents/ingest` trả về ngay khi document được ĐĂNG KÝ; chunk hoá,
    vector hoá và trích xuất chạy nền. Sync in "done" rồi thoát 0 ở đúng thời điểm chưa có gì
    được kiểm chứng — embedding hỏng thì tri thức nằm trong DB mà không có vector, search không
    bao giờ trả nó về, và không một lệnh nào trong chuỗi báo lỗi. Hỏng câm là kiểu hỏng tệ nhất:
    người dùng tin là mình đã ghi được.
    """
    if not doc_ids or wait_seconds <= 0:
        return [], list(doc_ids)

    import time

    wanted = set(doc_ids)
    deadline = time.time() + wait_seconds
    failed, pending, announced = [], list(wanted), False
    while True:
        by_id = fetch_documents(cfg, token, source_id)
        failed, pending = [], []
        for doc_id in wanted:
            doc = by_id.get(doc_id)
            if doc is None:
                # Document biến mất khỏi Brain sau khi ingest là mất dữ liệu, không phải "đang chạy".
                failed.append({"id": doc_id, "title": "?", "error": "document is gone from the brain"})
                continue
            status = str(doc.get("status") or "").lower()
            if status == TERMINAL_FAILED:
                failed.append({
                    "id": doc_id,
                    "title": doc.get("title") or doc.get("filename") or doc_id,
                    "error": doc.get("error") or "no reason reported",
                })
            elif status in IN_PROGRESS:
                pending.append(doc_id)
        if not pending or time.time() >= deadline:
            return failed, pending
        if not announced:
            print("[brain-sync] waiting for the brain to vectorise %d document(s) (up to %ds)..."
                  % (len(pending), wait_seconds))
            announced = True
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser(description="Brain sync (SAG)")
    ap.add_argument("--config", default=str(BRAIN_DIR / "brain.config"))
    ap.add_argument("--rebuild", action="store_true",
                    help="Xoá sạch source rồi ingest lại toàn bộ từ file")
    ap.add_argument("--no-verify", action="store_true",
                    help="Bỏ qua gate tools/verify.py (KHÔNG khuyến khích)")
    ap.add_argument("--no-wait", action="store_true",
                    help="Không chờ Brain vector hoá xong; sync sẽ KHÔNG phát hiện được document hỏng")
    args = ap.parse_args()

    run_verify(args.no_verify)

    cfg = load_config(args.config)
    state = load_state(cfg, args.rebuild)
    token = get_token(cfg)
    source_id = ensure_source(cfg, token, state)
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

    # Trạng thái hiện tại của document trong não. Không đọc cái này thì mọi lượt sync sau chỉ
    # nhìn sha256 và bỏ qua đúng những file đã hỏng ở lượt trước — file hỏng vĩnh viễn không
    # được thử lại, mà sync vẫn báo "done".
    existing = fetch_documents(cfg, token, source_id)

    seen, created, updated, deleted, skipped = set(), [], [], [], 0
    for p in files:
        r = rel(p)
        seen.add(r)
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        entry = state["files"].get(r)
        # Only skip if the document actually exists in the brain. Skipping when
        # state says "done" but the document was deleted by a previous crashed run
        # is the root cause of silent data loss — the agent trusts missing memory.
        #
        # Và chỉ skip khi document đó KHÔNG hỏng: file không đổi nhưng document đang `failed`
        # thì phải nạp lại, không phải bỏ qua.
        if entry and entry.get("sha256") == h and entry.get("document_id") and not args.rebuild:
            current = existing.get(entry["document_id"])
            healthy = current is not None and str(current.get("status") or "").lower() != TERMINAL_FAILED
            if healthy:
                skipped += 1
                continue
            print("  ! re-ingesting %s (the brain has it as %s)"
                  % (r, "failed" if current else "missing"))
        # Ingest the new document FIRST — never leave a gap.
        doc_id = ingest(cfg, token, source_id, r, p.read_text(encoding="utf-8"))
        old_doc_id = entry.get("document_id") if entry else None
        state["files"][r] = {"document_id": doc_id, "sha256": h}
        # Save state per file so a crash never loses all progress.
        save_state(cfg, state)
        # Delete old document only after the new one exists and state reflects it.
        if old_doc_id and old_doc_id != doc_id:
            delete_doc(cfg, token, source_id, old_doc_id)
        if entry:
            updated.append(r)
            print("  ~ update %s" % r)
        else:
            created.append(r)
            print("  + ingest %s" % r)

    for r in list(state["files"]):                    # file đã xoá trên đĩa
        if r not in seen:
            delete_doc(cfg, token, source_id, state["files"][r].get("document_id"))
            del state["files"][r]
            deleted.append(r)
            print("  - delete %s" % r)

    save_state(cfg, state)
    report_knowledge_sync(
        cfg,
        token,
        source_id,
        created=created,
        updated=updated,
        deleted=deleted,
        skipped=skipped,
        rebuild=args.rebuild,
    )
    print("[brain-sync] ingested: +%d ~%d -%d (skipped %d). source=%s (%s)"
          % (len(created), len(updated), len(deleted), skipped, cfg["BRAIN_SOURCE_NAME"], source_id))

    if args.no_wait:
        print("[brain-sync] --no-wait: NOT checking whether the brain vectorised anything.")
        print("[brain-sync] event/entity extraction runs in the background; wait for READY before searching.")
        return 0

    try:
        wait_seconds = int(cfg["BRAIN_SYNC_WAIT"])
    except (TypeError, ValueError):
        wait_seconds = 900
    # Kiểm TOÀN BỘ file đang được theo dõi, không chỉ file vừa gửi lượt này. Chỉ nhìn lượt này
    # thì một lượt sync không đổi file nào sẽ báo "done" trong khi não vẫn giữ document hỏng
    # từ lượt trước — đúng kiểu im lặng đang phải xoá bỏ.
    tracked = [e.get("document_id") for e in state["files"].values() if e.get("document_id")]
    failed, pending = await_documents(cfg, token, source_id, tracked, wait_seconds)

    for item in failed:
        print("  ! FAILED %s: %s" % (item["title"], item["error"]))
    if pending:
        print("[brain-sync] still processing after %ds: %d document(s). Check: npm run brain:logs"
              % (wait_seconds, len(pending)))

    if failed:
        # Exit khác 0. Đây là điểm mấu chốt: một lượt sync "thành công" trong khi document không
        # tới được trạng thái READY là tri thức đã mất mà không ai biết. CI, script và agent đều
        # đọc exit code — trả 0 ở đây là nói dối cả chuỗi phía sau.
        print("\n[brain-sync] FAILED: %d of %d document(s) did not reach READY."
              % (len(failed), len(tracked)))
        print("[brain-sync] They are NOT fully searchable. The reason for each file is printed above.")
        print("[brain-sync] Embedding errors  -> npm run embedding, then npm run brain:logs")
        print("[brain-sync] Extraction errors -> Settings -> Models (an LLM must be configured)")
        print("[brain-sync] Fix the cause, then run npm run sync again.")
        return 1

    if not pending:
        print("[brain-sync] done: every document is READY and searchable.")
    return 0


if __name__ == "__main__":
    _install_file_log()
    try:
        sys.exit(main() or 0)
    except SystemExit:
        raise
    except BaseException:
        # Traceback phải nằm trong file log, không chỉ trên terminal đã đóng.
        import traceback

        traceback.print_exc()
        print("[brain-sync] FAILED - details in %s" % LOG_FILE)
        raise
