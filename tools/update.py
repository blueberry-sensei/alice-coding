#!/usr/bin/env python3
"""update — nâng cấp template ALICE CODING mà KHÔNG đụng tri thức project.

Nguyên tắc: mỗi file trong knowledge/ thuộc đúng MỘT chủ sở hữu.

  TEMPLATE (luật, script, hướng dẫn)  -> update ghi đè được
  INSTANCE (tri thức project của bạn) -> update KHÔNG BAO GIỜ chạm vào

Danh giới nằm ở tools/manifest.json (sinh bởi --gen-manifest, do người bảo trì
template chạy). manifest ghi cả sha256 lúc phát hành, nên update phân biệt được
"file template bạn chưa từng sửa" (ghi đè an toàn) với "file template bạn đã sửa
tay" (không ghi đè — để lại bản .new và báo cáo).

Vì update tự fetch template vào thư mục tạm rồi áp theo manifest, knowledge/ KHÔNG
cần là git repo của template -> hết cảnh repo-lồng-repo và conflict khi git pull.

Chạy:
  python tools/update.py --check            # chỉ xem có bản mới không
  python tools/update.py                    # nâng cấp
  python tools/update.py --dry-run          # xem sẽ đổi gì, không ghi
  python tools/update.py --ref v2.1.0       # ghim version cụ thể
  python tools/update.py --gen-manifest     # (người bảo trì) sinh lại manifest
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                    # knowledge/
MANIFEST = HERE / "manifest.json"
REPO = os.environ.get("ALICE_TEMPLATE_REPO",
                      "https://github.com/blueberry-sensei/alice-coding")

# --- File thuộc TEMPLATE: update ghi đè (nếu người dùng chưa sửa tay) -------
TEMPLATE_GLOBS = [
    "VERSION", "LICENSE", ".gitattributes", ".gitignore",
    "README.md", "ALICE.md", "INITIALIZATION.md", "UPGRADE.md", "MIGRATIONS.md",
    "package.json",
    "tools/verify.py", "tools/update.py", "tools/cli.js", "tools/verify.config.example",
    "brain/*.md", "brain/brain.config.example", "brain/sync/*.py",
    # `*.js` là bắt buộc: brain-env.js tính danh tính brain và được CẢ HAI launcher gọi.
    # Thiếu nó thì người nâng cấp nhận launcher mới mà không có file nó gọi → brain không dựng được.
    "brain/stack/*.yaml", "brain/stack/*.sh", "brain/stack/*.ps1", "brain/stack/*.md",
    "brain/stack/*.js", "brain/stack/.env.example",
    "brain/stack/checklist/*",
    "wiki/README.md", "wiki/_TEMPLATE.md",
    "mistakes/README.md", "mistakes/_TEMPLATE.md",
    "decisions/README.md", "decisions/_TEMPLATE.md",
    "context/README.md", "context/_TEMPLATE.md",
    "changelog/README.md", "changelog/_TEMPLATE.md",
    "sub-agents/*.md", "sub-agents/*/*.md",
]

# --- File INSTANCE nhưng template có bản mồi: chỉ tạo KHI CHƯA CÓ ----------
SEED_FILES = [
    "ALICE.project.md", "wiki/ROUTER.md",
    "mistakes/LOG.md", "decisions/LOG.md", "context/INDEX.md",
]

# Mọi thứ còn lại (wiki/<module>.md, context/<digest>.md, changelog/<module>.md,
# brain/brain.config, tools/verify.config, prompts.md, .sag-data/...) là INSTANCE
# thuần: update không bao giờ đọc tới.


# Line-ending mà `git checkout` tạo ra, theo .gitattributes. Phải khớp file đó.
_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf"}
_CRLF_SUFFIXES = {".ps1", ".cmd", ".bat"}


def canonical_bytes(p):
    """Nội dung file NHƯ LÚC ĐƯỢC CHECKOUT, không phải như trên đĩa máy này.

    `.gitattributes` ép `* eol=lf` và `*.ps1|cmd|bat eol=crlf`. Working tree của
    người bảo trì có thể lệch (Windows hay giữ CRLF sau khi script ghi file), nên
    băm thẳng file trên đĩa sẽ sinh manifest KHÔNG BAO GIỜ khớp bản người dùng
    clone về — `update` sẽ tưởng file template bị sửa tay và từ chối ghi đè.
    Chuẩn hoá trước khi băm để manifest độc lập với OS của người bảo trì.
    """
    p = Path(p)
    raw = p.read_bytes()
    if p.suffix.lower() in _BINARY_SUFFIXES or b"\0" in raw:
        return raw
    body = raw.replace(b"\r\n", b"\n")
    if p.suffix.lower() in _CRLF_SUFFIXES:
        body = body.replace(b"\n", b"\r\n")
    return body


def sha(p):
    return hashlib.sha256(canonical_bytes(p)).hexdigest()


def collect(root):
    """Đường dẫn tương đối của mọi file khớp TEMPLATE_GLOBS, đã sắp xếp."""
    out = set()
    for pattern in TEMPLATE_GLOBS:
        for p in root.glob(pattern):
            if p.is_file():
                out.add(p.relative_to(root).as_posix())
    return sorted(out)


def read_version(root):
    vf = root / "VERSION"
    return vf.read_text(encoding="utf-8").strip() if vf.exists() else "0.0.0"


def vtuple(v):
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0, 0, 0])[:3]


# ------------------------------------------------------------------- fetch
def fetch_template(ref):
    """Tải template về thư mục tạm. Ưu tiên git, không có git thì tarball."""
    tmp = Path(tempfile.mkdtemp(prefix="alice-tpl-"))
    dest = tmp / "tpl"
    local = Path(REPO).expanduser()
    if shutil.which("git"):
        cmd = ["git", "clone", "--depth", "1", "--quiet"]
        if ref:
            cmd += ["--branch", ref]
        # ALICE_TEMPLATE_REPO có thể trỏ thư mục local (fork/thử nghiệm) hoặc URL.
        cmd += [str(local) if local.is_dir() else REPO + ".git", str(dest)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            shutil.rmtree(dest / ".git", ignore_errors=True)
            return tmp, dest
        print("[update] git clone failed (%s), falling back to the tarball..."
              % proc.stderr.strip().splitlines()[-1:] or "")
    url = "%s/archive/refs/heads/%s.tar.gz" % (REPO, ref or "main")
    if ref and ref.startswith("v"):
        url = "%s/archive/refs/tags/%s.tar.gz" % (REPO, ref)
    tgz = tmp / "t.tar.gz"
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tgz, "wb") as f:
            shutil.copyfileobj(r, f)
        with tarfile.open(tgz) as tf:
            tf.extractall(tmp)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit("[update] Could not download the template from %s (%s).\n"
                         "  Check your network, or set ALICE_TEMPLATE_REPO if you forked." % (url, e))
    for child in tmp.iterdir():
        if child.is_dir() and child.name != "tpl":
            return tmp, child
    shutil.rmtree(tmp, ignore_errors=True)
    raise SystemExit("[update] The tarball has no top-level directory as expected.")


# -------------------------------------------------------------- migrations
def m_2_0_0(root, dry):
    """1.x -> 2.0.0: tách phần đặc tả project khỏi file template."""
    notes = []
    if (root / "ALICE.md").exists() and not (root / "ALICE.project.md").exists():
        notes.append("create ALICE.project.md - move the project-specific appendix out "
                     "of ALICE.md into it (by hand: copy the tail of the old ALICE.md)")
    if not (root / "wiki" / "ROUTER.md").exists() and (root / "wiki" / "README.md").exists():
        notes.append("create wiki/ROUTER.md - move the Router + Dictionary tables out "
                     "of wiki/README.md into it (by hand)")
    if not (root / "decisions").exists():
        notes.append("add the decisions/ pillar - review the old context/ and split "
                     "the durable rules out into D-XXXX entries")
    return notes


MIGRATIONS = [("2.0.0", m_2_0_0)]


def run_migrations(root, old, new, dry):
    todo = []
    for ver, fn in MIGRATIONS:
        if vtuple(old) < vtuple(ver) <= vtuple(new):
            todo += ["[%s] %s" % (ver, n) for n in fn(root, dry)]
    return todo


# ------------------------------------------------------------------ actions
def gen_manifest():
    version = read_version(ROOT)
    files = {rel: sha(ROOT / rel) for rel in collect(ROOT)}
    MANIFEST.write_text(json.dumps(
        {"version": version, "generated": date.today().isoformat(), "files": files},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[update] wrote tools/manifest.json - version %s, %d template files."
          % (version, len(files)))
    return 0


def load_manifest():
    if not MANIFEST.exists():
        return {"version": read_version(ROOT), "files": {}}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Upgrade the ALICE CODING template")
    ap.add_argument("--check", action="store_true", help="only report whether a newer version exists")
    ap.add_argument("--dry-run", action="store_true", help="print the plan without writing anything")
    ap.add_argument("--ref", default=None, help="branch/tag to upgrade to (default: main)")
    ap.add_argument("--gen-manifest", action="store_true",
                    help="(maintainers) regenerate tools/manifest.json from the current tree")
    args = ap.parse_args()

    if args.gen_manifest:
        return gen_manifest()

    local_mf = load_manifest()
    local_ver = read_version(ROOT)
    tmp, tpl = fetch_template(args.ref)
    try:
        new_ver = read_version(tpl)
        print("[update] current: %s  ->  template: %s" % (local_ver, new_ver))
        if vtuple(new_ver) <= vtuple(local_ver) and not args.ref:
            print("[update] Already up to date. Nothing to do.")
            return 0
        if args.check:
            print("[update] A newer version exists. Run `python tools/update.py` to upgrade.")
            return 0

        new_files = collect(tpl)
        updated, added, conflicts, seeded, removed, unchanged = [], [], [], [], [], []

        for rel in new_files:
            src, dst = tpl / rel, ROOT / rel
            new_sha = sha(src)
            if not dst.exists():
                added.append(rel)
                continue
            cur_sha = sha(dst)
            if cur_sha == new_sha:
                unchanged.append(rel)
            elif cur_sha == local_mf["files"].get(rel):     # chưa sửa tay -> an toàn
                updated.append(rel)
            else:
                conflicts.append(rel)

        for rel in SEED_FILES:
            if not (ROOT / rel).exists() and (tpl / rel).exists():
                seeded.append(rel)

        for rel in local_mf["files"]:
            if rel not in new_files and (ROOT / rel).exists():
                removed.append(rel)

        notes = run_migrations(ROOT, local_ver, new_ver, args.dry_run)

        def show(label, items):
            if items:
                print("  %s (%d):" % (label, len(items)))
                for i in items:
                    print("    - %s" % i)

        print("\n[update] PLAN%s" % (" (dry-run)" if args.dry_run else ""))
        show("added", added)
        show("updated", updated)
        show("seeded (only when missing)", seeded)
        show("CONFLICT - you edited these, the new copy lands in *.new", conflicts)
        show("dropped from the template (left in place; delete if you want)", removed)
        print("  unchanged: %d template files" % len(unchanged))
        print("  UNTOUCHED: every wiki/<module>.md, mistakes/LOG.md, decisions/LOG.md,\n"
              "              context/*, changelog/<module>.md, ALICE.project.md, "
              "wiki/ROUTER.md, brain.config")

        if args.dry_run:
            if notes:
                print("\n[update] manual steps required after upgrading:")
                for n in notes:
                    print("    - %s" % n)
            return 0

        for rel in added + updated:
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tpl / rel, dst)
        for rel in seeded:
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tpl / rel, dst)
        for rel in conflicts:
            shutil.copy2(tpl / rel, ROOT / (rel + ".new"))

        tpl_mf = tpl / "tools" / "manifest.json"
        if tpl_mf.exists():
            shutil.copy2(tpl_mf, MANIFEST)
        else:                                   # template chưa kèm manifest -> tự dựng
            MANIFEST.write_text(json.dumps(
                {"version": new_ver, "generated": date.today().isoformat(),
                 "files": {rel: sha(tpl / rel) for rel in new_files}},
                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print("\n[update] DONE: +%d added | ~%d updated | %d seeded | %d conflicts"
              % (len(added), len(updated), len(seeded), len(conflicts)))
        if conflicts:
            print("[update] Resolving conflicts: diff `<file>` against `<file>.new`, merge by hand, "
                  "then delete the .new copy.")
        if notes:
            print("\n[update] MIGRATION steps you must do by hand:")
            for n in notes:
                print("    - %s" % n)
            print("  Details: MIGRATIONS.md")

        # `update` chỉ chép file template. Bản ứng dụng nằm trong image, và image chỉ được
        # kéo về khi dựng lại — nói rõ ở đây, kẻo người dùng tưởng nâng cấp xong là xong.
        print("\n[update] Next: `npm run verify` (required), then `npm run brain` to pull")
        print("         the matching application image - update only refreshes template files.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
