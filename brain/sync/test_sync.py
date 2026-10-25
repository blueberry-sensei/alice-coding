#!/usr/bin/env python3
"""Tests for brain/sync/sync.py: entry split, event derivation, verify gate, incremental plan.

Stdlib only. Run: npm run test:sync  (or python brain/sync/test_sync.py)
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync  # noqa: E402

LOG = """# Decisions LOG

## D-0002 · [2026-10-26] Hoàn tiền một cổng · #payments

- **Trạng thái:** ACTIVE
- **Loại:** quyết-định
- **Luật:**
  1. Mọi lệnh hoàn tiền đi qua `refundOrder()` ở `src/payments/refund.ts:12#refundOrder`.
     - Webhook chỉ ghi `payment_events`, không hoàn tiền.
  2. Gọi lại cùng `idempotency_key` trả kết quả lần đầu,
     không hoàn lần hai.
- **Vì sao:** thay D-0001 vì #double-charge.

## D-0001 · [2026-10-01] Luật cũ · #payments

- **Trạng thái:** SUPERSEDED → D-0002
- **Luật:** hoàn tiền ở nhiều nơi.
- **Sự kiện:**
  - Luật cũ cho phép hoàn tiền ở `legacyRefund()`.
  - Đã bị D-0002 thay
    vì gây hoàn tiền hai lần.
"""

WIKI = """# Payments

Mở bài của trang.

## Luồng

| Bước | Ai làm |
|---|---|
| Nhận webhook | `webhookHandler` |

```md
## không phải entry
```

## Luồng

Đoạn văn thứ hai của mục trùng tên.
"""


def entries_of(relpath, text):
    return {entry["title"]: entry for entry in sync.parse_entries(relpath, text)}


class EntryTests(unittest.TestCase):
    def test_log_entries_are_keyed_by_id_and_fences_do_not_split(self):
        log = entries_of("decisions/LOG.md", LOG)
        self.assertEqual(list(log), ["decisions/LOG.md", "decisions/LOG.md#D-0002", "decisions/LOG.md#D-0001"])
        d2 = log["decisions/LOG.md#D-0002"]
        self.assertEqual((d2["line"], d2["end_line"]), (3, 12))  # trailing blank line trimmed
        wiki = entries_of("wiki/payments.md", WIKI)
        self.assertEqual(list(wiki), ["wiki/payments.md", "wiki/payments.md#Luồng", "wiki/payments.md#Luồng~2"])
        self.assertIn("## không phải entry", wiki["wiki/payments.md#Luồng"]["text"])

    def test_hash_ignores_the_line_an_entry_starts_at(self):
        before = entries_of("decisions/LOG.md", LOG)["decisions/LOG.md#D-0001"]
        after = entries_of("decisions/LOG.md", "\n\n\n" + LOG)["decisions/LOG.md#D-0001"]
        self.assertEqual(before["sha256"], after["sha256"])
        self.assertEqual(after["line"], before["line"] + 3)

    def test_derived_events_carry_field_and_parent_context(self):
        events = entries_of("decisions/LOG.md", LOG)["decisions/LOG.md#D-0002"]["events"]
        by_line = {event["line"]: event for event in events}
        self.assertTrue(by_line[1]["title"].endswith("— Trạng thái: ACTIVE"))
        self.assertNotIn(3, by_line)  # Trạng thái lives in the heading event, not on its own
        self.assertEqual(by_line[6]["content"].split(" › ")[:2], ["D-0002 (ACTIVE)", "Luật"])
        self.assertTrue(by_line[7]["content"].startswith("D-0002 (ACTIVE) › Luật › Mọi lệnh hoàn tiền"))
        self.assertIn("không hoàn lần hai", by_line[8]["content"])  # continuation line joined
        names = {(entity["type"], entity["name"]) for entity in by_line[6]["entities"]}
        self.assertLessEqual(
            {("work", "D-0002"), ("concept", "#payments"), ("technology", "refundOrder()"),
             ("work", "src/payments/refund.ts")}, names)
        reasons = {(entity["type"], entity["name"]) for entity in by_line[10]["entities"]}
        self.assertLessEqual({("work", "D-0001"), ("concept", "#double-charge")}, reasons)

    def test_explicit_block_replaces_derived_events(self):
        events = entries_of("decisions/LOG.md", LOG)["decisions/LOG.md#D-0001"]["events"]
        self.assertEqual([event["line"] for event in events], [1, 6, 7])
        self.assertEqual(events[2]["title"], "Đã bị D-0002 thay vì gây hoàn tiền hai lần.")
        self.assertTrue(events[1]["content"].startswith("D-0001 (SUPERSEDED → D-0002) › "))

    def test_table_rows_and_paragraphs_become_events(self):
        wiki = entries_of("wiki/payments.md", WIKI)
        rows = [event["title"] for event in wiki["wiki/payments.md#Luồng"]["events"]]
        self.assertIn("Bước: Nhận webhook; Ai làm: `webhookHandler`", rows)
        self.assertFalse(any("không phải entry" in row for row in rows))  # code fences carry no event
        preamble = [event["title"] for event in wiki["wiki/payments.md"]["events"]]
        self.assertEqual(preamble, ["Payments", "Mở bài của trang."])


class VerifyGateTests(unittest.TestCase):
    def gate(self, items, paths=("decisions/LOG.md", "wiki/ROUTER.md")):
        entries = sync.parse_entries("decisions/LOG.md", LOG)
        report = json.dumps({"errors": len(items), "items": items})
        done = subprocess.CompletedProcess([], 1 if items else 0, stdout=report, stderr="")
        with mock.patch.object(sync.subprocess, "run", return_value=done), redirect_stdout(io.StringIO()) as out:
            return sync.verify_gate(False, entries, set(paths)), out.getvalue()

    def test_only_the_entry_holding_the_error_line_is_held(self):
        (held, files), _ = self.gate([{"level": "ERROR", "check": "C1", "msg": "gone", "file": "decisions/LOG.md", "line": 8},
                                      {"level": "WARN", "check": "C1", "msg": "drift", "file": "decisions/LOG.md", "line": 16}])
        self.assertEqual(list(held), ["decisions/LOG.md#D-0002"])
        self.assertEqual(files, set())

    def test_file_level_error_holds_the_whole_file_and_outside_scope_holds_nothing(self):
        (held, files), out = self.gate([{"level": "ERROR", "check": "C4", "msg": "x", "file": "decisions/LOG.md", "line": None},
                                        {"level": "ERROR", "check": "C9", "msg": "y", "file": "ALICE.project.md", "line": 3}])
        self.assertEqual(len(held), 3)
        self.assertEqual(files, {"decisions/LOG.md"})
        self.assertIn("outside the brain scope", out)

    def test_an_error_without_a_file_stops_the_sync(self):
        with self.assertRaises(SystemExit):
            self.gate([{"level": "ERROR", "check": "C?", "msg": "z", "file": None, "line": None}])


class FakeBrain:
    """Just enough of the brain API: documents become ready (or failed) as soon as they are ingested."""

    def __init__(self):
        self.docs, self.calls, self.fail_titles, self.old_image = {}, [], set(), False

    def __call__(self, method, url, token=None, data=None, timeout=None, tolerate=()):
        path = url.split("/api/v1", 1)[1]
        self.calls.append((method, path))
        if path == "/auth/login":
            return {"access_token": "t"}
        if path == "/sources":
            return [{"id": "s1", "name": os.environ["BRAIN_SOURCE_NAME"]}]
        if path.endswith("/documents/ingest-extracted"):
            if self.old_image:
                raise sync.HttpStatusError(405, "Method Not Allowed")
            doc_id = "d%d" % (len(self.docs) + 1)
            failed = data["title"] in self.fail_titles
            self.docs[doc_id] = {"id": doc_id, "filename": data["title"], "status": "failed" if failed else "ready",
                                 "origin_line": data["origin_line"], "error": "boom" if failed else None}
            return {"id": doc_id}
        if path.endswith("/documents/origins"):
            for item in data["items"]:
                self.docs[item["document_id"]]["origin_line"] = item["origin_line"]
            return {"ok": True}
        if path.endswith("/documents"):
            return list(self.docs.values())
        if method == "DELETE":
            self.docs.pop(path.rsplit("/", 1)[1], None)
            return {"ok": True}
        if path == "/telemetry/knowledge-sync":
            return {"recorded": True}
        raise AssertionError((method, path))

    def live(self):
        return sorted((doc["filename"], doc["origin_line"]) for doc in self.docs.values())


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "decisions").mkdir()
        self.log = self.tmp / "decisions" / "LOG.md"
        self.log.write_text(LOG, encoding="utf-8")
        self.brain = FakeBrain()
        self.held = ({}, set())
        env = {"BRAIN_ROOT": str(self.tmp), "STATE_FILE": str(self.tmp / "state.json"),
               "SAG_API_BASE": "http://fake/api/v1", "BRAIN_SOURCE_NAME": "test-knowledge",
               "BRAIN_INCLUDE": "decisions", "BRAIN_SYNC_WAIT": "5"}
        self.patches = [mock.patch.dict(os.environ, env), mock.patch.object(sync, "http", self.brain),
                        mock.patch.object(sync, "verify_gate", lambda *_: self.held),
                        mock.patch.object(sys, "argv", ["sync.py", "--config", str(self.tmp / "none.config")])]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def run_sync(self):
        with redirect_stdout(io.StringIO()) as out:
            code = sync.main()
        return code, out.getvalue()

    def test_new_changed_moved_held_and_removed_entries(self):
        code, out = self.run_sync()
        self.assertEqual(code, 0)
        self.assertIn("done: +3 ~0 -0 moved 0", out)
        first = self.brain.live()

        # Edit D-0002 without changing its length: one re-ingest, old copy removed after READY.
        self.log.write_text(LOG.replace("không hoàn lần hai.", "không bao giờ hoàn lần hai."), encoding="utf-8")
        code, out = self.run_sync()
        self.assertIn("done: +0 ~1 -0 moved 0 (unchanged 2, held back 0, old copies removed 1)", out)
        self.assertEqual(self.brain.live(), first)

        # One line inserted at the top: nothing re-embedded, every entry below only moves.
        text = "\n" + self.log.read_text(encoding="utf-8")
        self.log.write_text(text, encoding="utf-8")
        ingested = sum(1 for call in self.brain.calls if call[1].endswith("ingest-extracted"))
        code, out = self.run_sync()
        self.assertIn("done: +0 ~0 -0 moved 3", out)
        self.assertEqual(sum(1 for call in self.brain.calls if call[1].endswith("ingest-extracted")), ingested)
        self.assertEqual([line for _, line in self.brain.live()], [line + 1 for _, line in first])

        # A held entry keeps its brain copy even though it changed; the rest still syncs.
        self.log.write_text(text.replace("hoàn tiền ở nhiều nơi", "hoàn tiền khắp nơi"), encoding="utf-8")
        self.held = ({"decisions/LOG.md#D-0001": ["C1 gone (decisions/LOG.md:18)"]}, set())
        code, out = self.run_sync()
        self.assertEqual(code, 0)
        self.assertIn("= HELD decisions/LOG.md#D-0001", out)
        self.assertIn("held back 1", out)

        # Removing an entry deletes its document; a whole-file hold would have kept it.
        self.held = ({}, set())
        self.log.write_text(text[:text.index("## D-0001")], encoding="utf-8")
        code, out = self.run_sync()
        self.assertIn("-1", out.split("done:")[1])
        self.assertNotIn("decisions/LOG.md#D-0001", [name for name, _ in self.brain.live()])

    def test_a_failed_document_keeps_the_old_copy_and_exits_1(self):
        self.run_sync()
        self.log.write_text(LOG.replace("Luật cũ", "Luật xưa"), encoding="utf-8")
        self.brain.fail_titles = {"decisions/LOG.md#D-0001"}
        before = len(self.brain.docs)
        code, out = self.run_sync()
        self.assertEqual(code, 1)
        self.assertNotIn("done:", out)
        self.assertEqual(len(self.brain.docs), before + 1)  # nothing deleted while one copy failed

    def test_state_v2_documents_are_removed_only_after_entries_are_ready(self):
        self.brain.docs["old"] = {"id": "old", "filename": "LOG.md.md", "status": "ready", "origin_line": None}
        (self.tmp / "state.json").write_text(json.dumps(
            {"schema": 2, "source_id": "s1", "files": {"decisions/LOG.md": {"document_id": "old", "sha256": "x"}}}))
        code, out = self.run_sync()
        self.assertEqual(code, 0)
        self.assertNotIn("old", self.brain.docs)
        self.assertIn("old copies removed 1", out)

    def test_an_old_brain_image_stops_instead_of_falling_back(self):
        self.brain.old_image = True
        with self.assertRaises(SystemExit) as stop, redirect_stdout(io.StringIO()):
            sync.main()
        self.assertIn("npm run brain", str(stop.exception))


if __name__ == "__main__":
    unittest.main()
