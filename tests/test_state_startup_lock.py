from __future__ import annotations

import ast
import builtins
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_lock, state_startup_lock


_MISSING = object()


class StateStartupLockSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
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
        self.root = Path(self.temp_dir.name)
        self.lock_path = self.root / "wild-boar-proxy.lock"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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

    def recover(
        self,
        *,
        admitted_lock_path: Path | None = None,
        assessment_source_lock_path: Path | None | object = _MISSING,
        metadata: state_lock.LockMetadata | dict[str, object] | None = None,
        probe: state_lock.ProcessProbeResult | None = None,
        stale_after_seconds: float = 300,
    ) -> state_startup_lock.StartupLockSliceRecoveryResult:
        kwargs: dict[str, object] = {}
        if assessment_source_lock_path is not _MISSING:
            kwargs["assessment_source_lock_path"] = assessment_source_lock_path
        return state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path if admitted_lock_path is None else admitted_lock_path,
            self.metadata if metadata is None else metadata,
            self.matching_probe if probe is None else probe,
            now_utc=self.now,
            stale_after_seconds=stale_after_seconds,
            **kwargs,
        )

    def root_path(self, name: str) -> Path:
        return self.root / name

    def write_file(self, path: Path, payload: bytes = b"{}") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def no_follow(self, path: Path) -> str:
        return str(Path(os.path.abspath(os.path.normpath(os.fspath(path)))))

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

    def test_no_lock_inputs_and_missing_file_return_clean_recovery(self) -> None:
        result = state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path,
            None,
            None,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_RECOVERY_CLEAN,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertIsNone(result.deleted_lock_path)
        self.assertIsNotNone(result.assessment)

    def test_no_lock_inputs_and_existing_file_block_without_delete(self) -> None:
        self.write_file(self.lock_path, b"live")

        result = state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path,
            None,
            None,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertTrue(self.lock_path.exists())

    def test_clear_assessment_with_existing_file_returns_clean_without_delete(self) -> None:
        self.write_file(self.lock_path, b"live")

        result = self.recover(assessment_source_lock_path=self.lock_path)

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertTrue(self.lock_path.exists())

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

    def test_stale_assessment_deletes_exact_lock_file(self) -> None:
        self.write_file(self.lock_path, b"stale")

        result = self.recover(
            assessment_source_lock_path=self.lock_path,
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_lock.STATE_STARTUP_LOCK_SLICE_RECOVERY_RECOVERED,
        )
        self.assertTrue(result.cleanup_performed)
        self.assertEqual(result.deleted_lock_path, self.no_follow(self.lock_path))
        self.assertFalse(self.lock_path.exists())

    def test_stale_assessment_with_missing_file_returns_clean(self) -> None:
        result = self.recover(
            assessment_source_lock_path=self.lock_path,
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertIsNone(result.deleted_lock_path)

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

    def test_recycled_pid_stale_assessment_deletes_existing_lock_file(self) -> None:
        self.write_file(self.lock_path, b"stale")

        result = self.recover(
            assessment_source_lock_path=self.lock_path,
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=501,
                hostname="operator-host",
                process_create_time=999999.0,
            ),
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
        )
        self.assertFalse(self.lock_path.exists())

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

    def test_suspicious_assessment_blocks_and_preserves_file(self) -> None:
        self.write_file(self.lock_path, b"suspicious")

        result = self.recover(
            assessment_source_lock_path=self.lock_path,
            probe=state_lock.ProcessProbeResult(
                pid_exists=True,
                uid=777,
                hostname="operator-host",
                process_create_time=123456.75,
            ),
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertTrue(self.lock_path.exists())

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

    def test_invalid_assessment_blocks_and_preserves_file(self) -> None:
        self.write_file(self.lock_path, b"invalid")

        result = self.recover(
            assessment_source_lock_path=self.lock_path,
            metadata={"pid": 4242, "uid": 501},
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertFalse(result.cleanup_performed)
        self.assertTrue(self.lock_path.exists())

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

    def test_metadata_without_probe_blocks_recovery_and_preserves_file(self) -> None:
        self.write_file(self.lock_path, b"partial")

        result = state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path,
            self.metadata,
            None,
            assessment_source_lock_path=self.lock_path,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertTrue(self.lock_path.exists())

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

    def test_probe_without_metadata_blocks_recovery_and_preserves_file(self) -> None:
        self.write_file(self.lock_path, b"partial")

        result = state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path,
            None,
            self.matching_probe,
            assessment_source_lock_path=self.lock_path,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertTrue(self.lock_path.exists())

    def test_missing_assessment_source_blocks_when_facts_are_provided(self) -> None:
        self.write_file(self.lock_path, b"stale")

        result = state_startup_lock.run_startup_lock_slice_recovery(
            self.lock_path,
            self.metadata,
            self.matching_probe,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertIn("same-source", result.reason)
        self.assertTrue(self.lock_path.exists())

    def test_mismatched_assessment_source_blocks_without_delete(self) -> None:
        self.write_file(self.lock_path, b"stale")
        other_lock_path = self.root_path("other.lock")

        result = self.recover(
            assessment_source_lock_path=other_lock_path,
            probe=state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertIn("must match", result.reason)
        self.assertTrue(self.lock_path.exists())

    def test_relative_admitted_path_blocks(self) -> None:
        result = state_startup_lock.run_startup_lock_slice_recovery(
            Path("relative.lock"),
            None,
            None,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertIsNone(result.assessment)

    def test_symlink_path_blocks_without_follow_or_delete(self) -> None:
        target = self.write_file(self.root_path("outside.lock"), b"outside")
        symlink_lock = self.root_path("symlink.lock")
        symlink_lock.symlink_to(target)

        result = state_startup_lock.run_startup_lock_slice_recovery(
            symlink_lock,
            self.metadata,
            state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
            assessment_source_lock_path=symlink_lock,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertTrue(symlink_lock.is_symlink())
        self.assertTrue(target.exists())

    def test_directory_path_blocks_without_delete(self) -> None:
        directory_lock = self.root_path("directory.lock")
        directory_lock.mkdir()

        result = state_startup_lock.run_startup_lock_slice_recovery(
            directory_lock,
            self.metadata,
            state_lock.ProcessProbeResult(
                pid_exists=False,
                uid=None,
                hostname=None,
                process_create_time=None,
            ),
            assessment_source_lock_path=directory_lock,
            now_utc=self.now,
            stale_after_seconds=300,
        )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertTrue(directory_lock.exists())

    def test_assessment_does_not_touch_filesystem(self) -> None:
        def blocked_open(*_: object, **__: object) -> object:
            raise AssertionError("lock slice assessment must not touch filesystem")

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lock.json"
            with mock.patch.object(builtins, "open", blocked_open):
                result = self.assess()

            self.assertEqual(result.lock_slice_outcome, state_startup_lock.LOCK_SLICE_CLEAR)
            self.assertFalse(path.exists())

    def test_recovery_does_not_parse_lock_file_or_probe_processes(self) -> None:
        self.write_file(self.lock_path, b"stale")

        def blocked_open(*_: object, **__: object) -> object:
            raise AssertionError("lock slice recovery must not parse lock files")

        with (
            mock.patch.object(builtins, "open", blocked_open),
            mock.patch.object(state_lock, "_coerce_metadata", wraps=state_lock._coerce_metadata) as coerce,
        ):
            result = self.recover(
                assessment_source_lock_path=self.lock_path,
                probe=state_lock.ProcessProbeResult(
                    pid_exists=False,
                    uid=None,
                    hostname=None,
                    process_create_time=None,
                ),
            )

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
        )
        coerce.assert_called_once()

    def test_result_dataclass_does_not_expose_packet_startup_or_rollback_fields(self) -> None:
        field_names = set(state_startup_lock.StartupLockSliceAssessment.__dataclass_fields__)
        recovery_field_names = set(
            state_startup_lock.StartupLockSliceRecoveryResult.__dataclass_fields__
        )
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
        self.assertTrue(forbidden.isdisjoint(recovery_field_names))

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
