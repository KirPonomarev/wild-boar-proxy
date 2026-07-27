from __future__ import annotations

import ast
import builtins
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_lock


class StateLockOwnerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.metadata = state_lock.LockMetadata(
            pid=4242,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
            started_at_utc="2026-06-01T11:59:00+00:00",
            command="wbp sync --json",
        )
        self.matching_probe = state_lock.ProcessProbeResult(
            pid_exists=True,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
        )

    def classify(
        self,
        metadata: state_lock.LockMetadata | dict[str, object] | None = None,
        probe: state_lock.ProcessProbeResult | None = None,
        *,
        stale_after_seconds: float = 300,
    ) -> state_lock.LockOwnerClassification:
        return state_lock.classify_lock_owner(
            self.metadata if metadata is None else metadata,
            self.matching_probe if probe is None else probe,
            now_utc=self.now,
            stale_after_seconds=stale_after_seconds,
        )

    def test_process_not_alive_is_stale(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_STALE)
        self.assertEqual(result.machine_error_code, state_lock.STATE_LOCK_STALE)

    def test_same_owner_live_process_is_active(self) -> None:
        result = self.classify()

        self.assertEqual(result.status, state_lock.LOCK_ACTIVE)
        self.assertEqual(result.machine_error_code, state_lock.STATE_LOCK_ACTIVE)

    def test_mapping_metadata_classifies_like_dataclass_metadata(self) -> None:
        metadata = {
            "pid": 4242,
            "uid": 501,
            "hostname": "operator-host",
            "process_create_time": 123456.75,
            "started_at_utc": "2026-06-01T11:59:00+00:00",
            "command": "wbp sync --json",
        }

        result = self.classify(metadata=metadata)

        self.assertEqual(result.status, state_lock.LOCK_ACTIVE)

    def test_pid_reuse_create_time_mismatch_is_stale(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=999999.0,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_STALE)
        self.assertIn("recycled", result.reason)

    def test_near_create_time_mismatch_is_stale(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=123456.750001,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_STALE)

    def test_uid_mismatch_is_suspicious(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=502,
                hostname="operator-host",
                process_create_time=123456.75,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_SUSPICIOUS)
        self.assertEqual(result.machine_error_code, state_lock.STATE_LOCK_SUSPICIOUS)

    def test_hostname_mismatch_is_suspicious(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="other-host",
                process_create_time=123456.75,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_SUSPICIOUS)
        self.assertEqual(result.machine_error_code, state_lock.STATE_LOCK_SUSPICIOUS)

    def test_live_process_without_create_time_is_suspicious(self) -> None:
        result = self.classify(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=None,
            )
        )

        self.assertEqual(result.status, state_lock.LOCK_SUSPICIOUS)

    def test_missing_required_metadata_is_invalid(self) -> None:
        result = self.classify(metadata={"pid": 4242, "uid": 501})

        self.assertEqual(result.status, state_lock.LOCK_INVALID)
        self.assertEqual(result.machine_error_code, state_lock.STATE_LOCK_INVALID)

    def test_malformed_metadata_is_invalid(self) -> None:
        result = self.classify(
            metadata={
                "pid": -1,
                "uid": 501,
                "hostname": "operator-host",
                "process_create_time": 123456.75,
                "started_at_utc": "not-a-date",
                "command": "wbp sync --json",
            }
        )

        self.assertEqual(result.status, state_lock.LOCK_INVALID)

    def test_bool_pid_or_uid_metadata_is_invalid(self) -> None:
        for metadata in (
            {
                "pid": True,
                "uid": 501,
                "hostname": "operator-host",
                "process_create_time": 123456.75,
                "started_at_utc": "2026-06-01T11:59:00+00:00",
                "command": "wbp sync --json",
            },
            {
                "pid": 4242,
                "uid": False,
                "hostname": "operator-host",
                "process_create_time": 123456.75,
                "started_at_utc": "2026-06-01T11:59:00+00:00",
                "command": "wbp sync --json",
            },
        ):
            result = self.classify(metadata=metadata)

            self.assertEqual(result.status, state_lock.LOCK_INVALID)

    def test_old_lock_with_dead_owner_is_stale(self) -> None:
        old_metadata = state_lock.LockMetadata(
            pid=4242,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
            started_at_utc="2026-06-01T11:00:00+00:00",
            command="wbp sync --json",
        )

        result = self.classify(
            metadata=old_metadata,
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
            stale_after_seconds=300,
        )

        self.assertEqual(result.status, state_lock.LOCK_STALE)

    def test_old_lock_with_ambiguous_live_owner_is_suspicious_not_stale(self) -> None:
        old_metadata = state_lock.LockMetadata(
            pid=4242,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
            started_at_utc="2026-06-01T11:00:00+00:00",
            command="wbp sync --json",
        )

        result = self.classify(
            metadata=old_metadata,
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=502,
                hostname="operator-host",
                process_create_time=123456.75,
            ),
            stale_after_seconds=300,
        )

        self.assertEqual(result.status, state_lock.LOCK_SUSPICIOUS)

    def test_old_lock_with_same_owner_live_process_remains_active(self) -> None:
        old_metadata = state_lock.LockMetadata(
            pid=4242,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
            started_at_utc="2026-06-01T11:00:00+00:00",
            command="wbp sync --json",
        )

        result = self.classify(metadata=old_metadata, stale_after_seconds=300)

        self.assertEqual(result.status, state_lock.LOCK_ACTIVE)
        self.assertIn("old", result.reason)

    def test_zero_threshold_does_not_make_same_owner_live_lock_stale(self) -> None:
        result = self.classify(stale_after_seconds=0)

        self.assertEqual(result.status, state_lock.LOCK_ACTIVE)

    def test_negative_threshold_does_not_make_same_owner_live_lock_stale(self) -> None:
        result = self.classify(stale_after_seconds=-1)

        self.assertEqual(result.status, state_lock.LOCK_ACTIVE)

    def test_classifier_does_not_read_or_write_filesystem(self) -> None:
        def blocked_open(*_: object, **__: object) -> object:
            raise AssertionError("classifier must not touch filesystem")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lock.json"
            with mock.patch.object(builtins, "open", blocked_open):
                result = self.classify()

            self.assertEqual(result.status, state_lock.LOCK_ACTIVE)
            self.assertFalse(path.exists())

    def test_state_lock_does_not_import_runtime_layers(self) -> None:
        source = Path(state_lock.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {
            "os",
            "pathlib",
            "psutil",
            "subprocess",
            "wild_boar_proxy.runtime",
            "wild_boar_proxy.operator_surface",
            "wild_boar_proxy.cli",
            "wild_boar_proxy.web_design_live_server",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
