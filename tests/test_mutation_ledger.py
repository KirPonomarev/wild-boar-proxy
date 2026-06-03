from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import mutation_ledger


class MutationLedgerTests(unittest.TestCase):
    def test_build_mutation_ledger_fields_reports_file_replace_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            path.write_text('{"value":1}\n', encoding="utf-8")
            before = mutation_ledger.snapshot_paths([path])
            path.write_text('{"value":2}\n', encoding="utf-8")
            after = mutation_ledger.snapshot_paths([path])

            fields = mutation_ledger.build_mutation_ledger_fields(
                effect="repair",
                scope="healthcheck_repair",
                changed_files=[path],
                before=before,
                after=after,
            )

        self.assertRegex(fields["mutation_id"], r"^wbp-mut-[0-9a-f]{20}$")
        ledger = fields["mutation_ledger"]
        self.assertEqual(ledger["schema_version"], 1)
        self.assertEqual(ledger["status"], "mutated")
        self.assertEqual(ledger["effect"], "repair")
        self.assertEqual(ledger["scope"], "healthcheck_repair")
        self.assertFalse(ledger["rollback_available"])
        self.assertIsNone(ledger["rollback_id"])
        self.assertEqual(ledger["rollback_phase"], "ledger_only")
        record = ledger["changed_files"][0]
        self.assertEqual(record["path"], str(path))
        self.assertEqual(record["kind"], "file")
        self.assertEqual(record["operation"], "replace")
        self.assertEqual(record["before_kind"], "file")
        self.assertEqual(record["after_kind"], "file")
        self.assertIsInstance(record["before_sha256"], str)
        self.assertIsInstance(record["after_sha256"], str)
        self.assertNotEqual(record["before_sha256"], record["after_sha256"])

    def test_build_mutation_ledger_fields_reports_delete_without_fake_after_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "stale.lock"
            path.write_text("999999\n", encoding="utf-8")
            before = mutation_ledger.snapshot_paths([path])
            path.unlink()
            after = mutation_ledger.snapshot_paths([path])

            fields = mutation_ledger.build_mutation_ledger_fields(
                effect="repair",
                scope="healthcheck_repair",
                changed_files=[path],
                before=before,
                after=after,
            )

        record = fields["mutation_ledger"]["changed_files"][0]
        self.assertEqual(record["kind"], "missing")
        self.assertEqual(record["operation"], "delete")
        self.assertEqual(record["before_kind"], "file")
        self.assertEqual(record["after_kind"], "missing")
        self.assertIsInstance(record["before_sha256"], str)
        self.assertIsNone(record["after_sha256"])

    def test_build_mutation_ledger_fields_reports_not_mutated_without_id(self) -> None:
        fields = mutation_ledger.build_mutation_ledger_fields(
            effect="repair",
            scope="healthcheck_repair",
            changed_files=[],
            before={},
            after={},
        )

        self.assertIsNone(fields["mutation_id"])
        ledger = fields["mutation_ledger"]
        self.assertEqual(ledger["status"], "not_mutated")
        self.assertEqual(ledger["changed_files"], [])
        self.assertFalse(ledger["rollback_available"])
        self.assertIsNone(ledger["rollback_id"])


if __name__ == "__main__":
    unittest.main()
