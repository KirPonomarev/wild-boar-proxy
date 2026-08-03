# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B04: Thread Context Ledger V2 tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import thread_context_ledger as tcl


def _make_ledger(root: Path, **kwargs) -> tcl.ThreadContextLedger:
    return tcl.ThreadContextLedger(root, thread_id="thread-1", **kwargs)


class LedgerCoreTests(unittest.TestCase):
    def _ledger(self, root: Path, **kwargs) -> tcl.ThreadContextLedger:
        return _make_ledger(root, **kwargs)

    def test_append_and_revision_monotonic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir))
            for index in range(3):
                packet = ledger.append(
                    entry_id=f"e{index}",
                    kind=tcl.ENTRY_USER_VISIBLE,
                    content=f"message {index}",
                    source="hook",
                    context_digest=f"ctx-{index}",
                )
                self.assertEqual(packet["status"], "ok")
                self.assertEqual(packet["revision"], index + 1)
            snapshot = ledger.snapshot()
            self.assertEqual(snapshot["revision"], 3)
            self.assertEqual(snapshot["entry_count"], 3)
            self.assertTrue(snapshot["context_digest"])

    def test_duplicate_entry_id_rejected_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir))
            ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="ctx-1",
            )
            packet = ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="ctx-1",
            )
            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["duplicate_rejected"])
            self.assertEqual(ledger.snapshot()["entry_count"], 1)

    def test_secrets_never_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger.append(
                entry_id="e1",
                kind=tcl.ENTRY_USER_VISIBLE,
                content="my api key sk-live-abcdef123456 and Bearer tok1234567890",
                source="hook",
                context_digest="ctx-1",
            )
            snapshot = ledger.snapshot()
            self.assertNotIn("sk-live-abcdef123456", json.dumps(snapshot))
            self.assertNotIn("tok1234567890", json.dumps(snapshot))
            on_disk = (root / "thread-1" / "ledger.json").read_text(encoding="utf-8")
            self.assertNotIn("sk-live", on_disk)
            self.assertNotIn("Bearer tok", on_disk)

    def test_missing_context_digest_is_degraded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir))
            packet = ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="",
            )
            self.assertEqual(packet["status"], "degraded")
            self.assertEqual(packet["machine_error_code"], "ledger_context_digest_missing")

    def test_oversized_entry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir), max_entry_bytes=32)
            packet = ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="x" * 200,
                source="hook", context_digest="ctx-1",
            )
            self.assertEqual(packet["status"], "degraded")
            self.assertEqual(packet["machine_error_code"], "ledger_entry_too_large")

    def test_size_limit_keeps_newest_and_advances_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir), max_entries=2)
            for index in range(5):
                ledger.append(
                    entry_id=f"e{index}", kind=tcl.ENTRY_USER_VISIBLE,
                    content=f"m{index}", source="hook", context_digest=f"ctx-{index}",
                )
            snapshot = ledger.snapshot()
            self.assertEqual(snapshot["entry_count"], 2)
            # generation advanced once per size-limit trim (3 trims for 5
            # appends with max_entries=2)
            self.assertEqual(snapshot["generation"], 4)
            self.assertEqual(snapshot["entries"][0]["entry_id"], "e3")

    def test_ttl_expiry_prunes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir), ttl_seconds=0)
            ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="ctx-1",
            )
            snapshot = ledger.snapshot()
            self.assertEqual(snapshot["pruned_expired"], 1)
            self.assertEqual(snapshot["entry_count"], 0)

    def test_per_thread_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = tcl.ThreadContextLedger(root, thread_id="t1")
            second = tcl.ThreadContextLedger(root, thread_id="t2")
            first.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="ctx-1",
            )
            self.assertEqual(second.snapshot()["entry_count"], 0)

    def test_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="a",
                source="hook", context_digest="ctx-1",
            )
            mode = os.stat(root / "thread-1" / "ledger.json").st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_reload_persists_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE, content="hello",
                source="hook", context_digest="ctx-1",
            )
            reloaded = tcl.ThreadContextLedger(root, thread_id="thread-1")
            self.assertEqual(reloaded.snapshot()["entry_count"], 1)
            self.assertEqual(reloaded.snapshot()["revision"], 1)


class RecoveryTests(unittest.TestCase):
    def _ledger(self, root: Path, **kwargs) -> tcl.ThreadContextLedger:
        return _make_ledger(root, **kwargs)
    def test_corrupt_tail_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self._ledger(root)
            for index in range(3):
                ledger.append(
                    entry_id=f"e{index}", kind=tcl.ENTRY_USER_VISIBLE,
                    content=f"m{index}", source="hook", context_digest=f"ctx-{index}",
                )
            # Corrupt the persisted document: append a bogus entry.
            path = root / "thread-1" / "ledger.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["entries"].append({"entry_id": "x", "revision": 99, "kind": "broken"})
            path.write_text(json.dumps(document), encoding="utf-8")
            recovered = tcl.ThreadContextLedger(root, thread_id="thread-1")
            self.assertTrue(recovered.recovered)
            snapshot = recovered.snapshot()
            self.assertEqual(snapshot["entry_count"], 3)
            self.assertEqual(snapshot["revision"], 3)

    def test_unreadable_ledger_fails_with_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            thread_root = root / "thread-1"
            thread_root.mkdir(mode=0o700)
            (thread_root / "ledger.json").write_text("{not-json", encoding="utf-8")
            ledger = tcl.ThreadContextLedger(root, thread_id="thread-1")
            self.assertEqual(ledger.status, "failed")
            self.assertEqual(ledger.snapshot()["status"], "failed")

    def test_escaped_thread_root_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(ValueError):
                tcl.ThreadContextLedger(root, thread_id="../../etc")


class DigestTests(unittest.TestCase):
    def _ledger(self, root: Path, **kwargs) -> tcl.ThreadContextLedger:
        return _make_ledger(root, **kwargs)
    def test_digest_stable_for_same_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = self._ledger(Path(temp_dir))
            second = tcl.ThreadContextLedger(Path(temp_dir), thread_id="thread-2")
            for index in range(2):
                for ledger in (first, second):
                    ledger.append(
                        entry_id=f"e{index}", kind=tcl.ENTRY_USER_VISIBLE,
                        content=f"m{index}", source="hook", context_digest=f"ctx-{index}",
                    )
            self.assertEqual(first.snapshot()["context_digest"], second.snapshot()["context_digest"])

    def test_redaction_changes_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ledger = self._ledger(Path(temp_dir))
            ledger.append(
                entry_id="e1", kind=tcl.ENTRY_USER_VISIBLE,
                content="key sk-live-abcdef123456", source="hook", context_digest="ctx-1",
            )
            digest = ledger.snapshot()["context_digest"]
            self.assertNotEqual(digest, tcl.context_digest([]))


if __name__ == "__main__":
    unittest.main()
