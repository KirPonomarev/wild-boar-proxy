from __future__ import annotations

import ast
import builtins
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_lock, state_startup_lock


class StateStartupLockSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
        self.metadata = state_lock.LockMetadata(
            pid=4242,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
            started_at_utc="2026-06-02T11:59:00+00:00",
            command="wbp sync --json",
        )
        self.matching_probe = state_lock.ProcessProbeResult(
            pid_exists=True,
            uid=501,
            hostname="operator-host",
            process_create_time=123456.75,
        )

    def assess(
        self,
        *,
        metadata: state_lock.LockMetadata | dict[str, object] | None = None,
        probe: state_lock.ProcessProbeResult | None = None,
        stale_after_seconds: float = 300,
    ) -> state_startup_lock.StartupLockSliceAssessment:
        return state_startup_lock.assess_startup_lock_slice(
            self.metadata if metadata is None else metadata,
            self.matching_probe if probe is None else probe,
            now_utc=self.now,
            stale_after_seconds=stale_after_seconds,
        )

    def test_no_lock_inputs_return_clear_slice(self) -> None:
        result = state_startup_lock.assess_startup_lock_slice(
            None,
            None,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_CLEAR)
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_CLEAR,
        )
        self.assertIsNone(result.owner_classification)

    def test_matching_live_owner_returns_clear_slice(self) -> None:
        result = self.assess()

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_CLEAR)
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_CLEAR,
        )
        self.assertIsNotNone(result.owner_classification)
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_ACTIVE)

    def test_dead_pid_returns_stale_slice(self) -> None:
        result = self.assess(
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            )
        )

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_STALE)
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_STALE,
        )
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_STALE)

    def test_recycled_pid_returns_stale_slice(self) -> None:
        result = self.assess(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=999999.0,
            )
        )

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_STALE)
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_STALE)

    def test_uid_mismatch_returns_suspicious_slice(self) -> None:
        result = self.assess(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=777,
                hostname="operator-host",
                process_create_time=123456.75,
            )
        )

        self.assertEqual(
            result.lock_slice_outcome,
            state_startup_lock.LOCK_SLICE_SUSPICIOUS,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_SUSPICIOUS,
        )
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_SUSPICIOUS)

    def test_hostname_mismatch_returns_suspicious_slice(self) -> None:
        result = self.assess(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="other-host",
                process_create_time=123456.75,
            )
        )

        self.assertEqual(
            result.lock_slice_outcome,
            state_startup_lock.LOCK_SLICE_SUSPICIOUS,
        )
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_SUSPICIOUS)

    def test_missing_create_time_returns_suspicious_slice(self) -> None:
        result = self.assess(
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=None,
            )
        )

        self.assertEqual(
            result.lock_slice_outcome,
            state_startup_lock.LOCK_SLICE_SUSPICIOUS,
        )
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_SUSPICIOUS)

    def test_invalid_metadata_returns_invalid_slice(self) -> None:
        result = self.assess(metadata={"pid": 4242, "uid": 501})

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_INVALID)
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_INVALID,
        )
        assert result.owner_classification is not None
        self.assertEqual(result.owner_classification.status, state_lock.LOCK_INVALID)

    def test_metadata_without_probe_returns_invalid_slice(self) -> None:
        result = state_startup_lock.assess_startup_lock_slice(
            self.metadata,
            None,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_INVALID)
        self.assertIsNone(result.owner_classification)
        self.assertIn("both be provided", result.reason)

    def test_probe_without_metadata_returns_invalid_slice(self) -> None:
        result = state_startup_lock.assess_startup_lock_slice(
            None,
            self.matching_probe,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_INVALID)
        self.assertIsNone(result.owner_classification)
        self.assertIn("both be provided", result.reason)

    def test_assessment_does_not_touch_filesystem(self) -> None:
        def blocked_open(*_: object, **__: object) -> object:
            raise AssertionError("lock slice assessment must not touch filesystem")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lock.json"
            with mock.patch.object(builtins, "open", blocked_open):
                result = self.assess()

            self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_CLEAR)
            self.assertFalse(path.exists())

    def test_result_dataclass_does_not_expose_packet_startup_or_rollback_fields(self) -> None:
        field_names = set(state_startup_lock.StartupLockSliceAssessment.__dataclass_fields__)
        forbidden = {
            "status",
            "effect",
            "exit_code",
            "human_message",
            "next_action",
            "operator_action",
            "changed_files",
            "startup_clean",
            "auto_recovered",
            "repair_required",
            "rollback_available",
            "rollback_id",
        }
        self.assertTrue(forbidden.isdisjoint(field_names))

    def test_state_startup_lock_does_not_import_runtime_layers(self) -> None:
        source = Path(state_startup_lock.__file__).read_text(encoding="utf-8")
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
            "wild_boar_proxy.command_effects",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
