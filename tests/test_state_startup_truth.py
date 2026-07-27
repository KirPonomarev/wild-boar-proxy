from __future__ import annotations

import ast
import tempfile
import unittest
import json
from pathlib import Path
from unittest import mock

from wild_boar_proxy import state_startup_truth


class StateStartupTruthSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry_path = self.root / "backend-registry.json"
        self.state_path = self.root / "supervisor-state.json"
        self.effective_mode_path = self.root / "runtime-effective-mode.txt"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def truth_paths(
        self,
        *,
        registry_path: Path | None = None,
        supervisor_state_path: Path | None = None,
        runtime_effective_mode_path: Path | None = None,
    ) -> state_startup_truth.StartupRuntimeTruthPaths:
        return state_startup_truth.StartupRuntimeTruthPaths(
            registry_path=self.registry_path if registry_path is None else registry_path,
            supervisor_state_path=self.state_path
            if supervisor_state_path is None
            else supervisor_state_path,
            runtime_effective_mode_path=self.effective_mode_path
            if runtime_effective_mode_path is None
            else runtime_effective_mode_path,
        )

    def write_text(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json_like(self, path: Path, payload: str) -> Path:
        return self.write_text(path, payload)

    def selected_backend_snapshot(
        self,
        ids: list[str] | None = None,
        **overrides: object,
    ) -> dict[str, object]:
        selected_ids = ["backend-a", "backend-b"] if ids is None else ids
        snapshot: dict[str, object] = {
            "schema_version": 1,
            "snapshot_kind": "selected_backend_participation",
            "source_class": "supervisor_owner_observed",
            "source_name": "sync --json",
            "source_run_id": "run-1",
            "producer_version": "producer-1",
            "observed_at_utc": "2026-06-02T12:00:00+00:00",
            "selected_backend_ids": selected_ids,
            "selected_backends_digest": state_startup_truth._selected_backend_ids_digest(
                tuple(sorted(selected_ids))
            ),
            "claim_scope": "bounded_local_participation_evidence_only",
        }
        snapshot.update(overrides)
        return snapshot

    def registry_payload(self, *, stable_default_backend_id: str = "backend-a") -> str:
        return (
            "{\n"
            '  "schema_version": 2,\n'
            '  "version": "v1",\n'
            '  "updated_at": "2026-06-02T12:00:00+00:00",\n'
            f'  "stable_default_backend_id": "{stable_default_backend_id}",\n'
            '  "pool_policy": {"active_min": 1, "active_target": 1, "reserve_target": 0},\n'
            '  "backends": []\n'
            "}\n"
        )

    def state_payload(
        self,
        *,
        effective_mode: str = "stable",
        stable_default_backend_id: str = "backend-a",
        selected_backend_snapshot: dict[str, object] | None = None,
    ) -> str:
        snapshot_fragment = ""
        if selected_backend_snapshot is not None:
            import json

            snapshot_fragment = ',\n  "selected_backend_snapshot": ' + json.dumps(
                selected_backend_snapshot,
                sort_keys=True,
            )
        return (
            "{\n"
            '  "schema_version": 1,\n'
            '  "version": "v1",\n'
            '  "status": "stable",\n'
            f'  "effective_mode": "{effective_mode}",\n'
            '  "last_sync_at": "2026-06-02T12:00:00+00:00",\n'
            '  "last_error": "",\n'
            '  "selected_backend_ids": ["backend-a", "backend-b"],\n'
            '  "managed_port": 8320,\n'
            '  "current_proxy_url": "http://127.0.0.1:8318",\n'
            f'  "stable_default_backend_id": "{stable_default_backend_id}"'
            f"{snapshot_fragment}\n"
            "}\n"
        )

    def assess(
        self,
        *,
        paths: state_startup_truth.StartupRuntimeTruthPaths | None = None,
    ) -> state_startup_truth.StartupTruthSliceAssessment:
        return state_startup_truth.assess_startup_truth_slice(
            self.truth_paths() if paths is None else paths
        )

    def test_relative_registry_path_blocks(self) -> None:
        result = self.assess(
            paths=self.truth_paths(registry_path=Path("backend-registry.json"))
        )

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_truth.STATE_STARTUP_TRUTH_SLICE_BLOCKED,
        )

    def test_symlink_path_blocks(self) -> None:
        registry_target = self.write_json_like(
            self.root / "registry-target.json",
            self.registry_payload(),
        )
        symlink = self.root / "backend-registry-link.json"
        symlink.symlink_to(registry_target)

        result = self.assess(paths=self.truth_paths(registry_path=symlink))

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )

    def test_directory_path_blocks(self) -> None:
        self.registry_path.mkdir()

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )

    def test_missing_registry_blocks(self) -> None:
        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )
        self.assertFalse(result.registry_present)

    def test_missing_supervisor_state_blocks(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )
        self.assertTrue(result.registry_present)
        self.assertFalse(result.supervisor_state_present)

    def test_missing_runtime_effective_mode_returns_partial(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(self.state_path, self.state_payload())

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_PARTIAL,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_truth.STATE_STARTUP_TRUTH_SLICE_PARTIAL,
        )
        self.assertFalse(result.effective_mode_artifact_present)

    def test_corrupt_registry_blocks(self) -> None:
        self.write_json_like(self.registry_path, "{not-json")
        self.write_json_like(self.state_path, self.state_payload())

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )

    def test_corrupt_supervisor_state_blocks(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(self.state_path, "{not-json")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )

    def test_stable_default_backend_id_mismatch_is_contradicted(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload(stable_default_backend_id="backend-a"))
        self.write_json_like(
            self.state_path,
            self.state_payload(stable_default_backend_id="backend-b"),
        )
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONTRADICTED,
        )
        self.assertEqual(
            result.machine_error_code,
            state_startup_truth.STATE_STARTUP_TRUTH_SLICE_CONTRADICTED,
        )
        self.assertIn("stable_default_backend_id", result.contradiction_fields)

    def test_effective_mode_mismatch_is_contradicted(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(self.state_path, self.state_payload(effective_mode="managed"))
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONTRADICTED,
        )
        self.assertIn("effective_mode", result.contradiction_fields)

    def test_absent_selected_backend_snapshot_does_not_block_consistent_truth(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(self.state_path, self.state_payload())
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONSISTENT,
        )
        self.assertFalse(result.selected_backend_snapshot_present)

    def test_valid_selected_backend_snapshot_keeps_consistent_truth(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(
            self.state_path,
            self.state_payload(
                selected_backend_snapshot=self.selected_backend_snapshot()
            ),
        )
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONSISTENT,
        )
        self.assertTrue(result.selected_backend_snapshot_present)

    def test_invalid_selected_backend_snapshot_shape_blocks(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(
            self.state_path,
            self.state_payload(
                selected_backend_snapshot=self.selected_backend_snapshot(source_run_id="")
            ),
        )
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_BLOCKED,
        )
        self.assertTrue(result.selected_backend_snapshot_present)

    def test_invalid_selected_backend_snapshot_variants_block(self) -> None:
        malformed_snapshots: list[object] = [
            "not-a-dict",
            self.selected_backend_snapshot(schema_version=2),
            self.selected_backend_snapshot(snapshot_kind="wrong-kind"),
            self.selected_backend_snapshot(source_class="registry_synthesized"),
            self.selected_backend_snapshot(observed_at_utc=""),
            self.selected_backend_snapshot(selected_backend_ids=[]),
            self.selected_backend_snapshot(claim_scope="wrong-scope"),
        ]

        for malformed_snapshot in malformed_snapshots:
            with self.subTest(snapshot=malformed_snapshot):
                self.write_json_like(self.registry_path, self.registry_payload())
                state_payload = {
                    "schema_version": 1,
                    "version": "v1",
                    "status": "stable",
                    "effective_mode": "stable",
                    "last_sync_at": "2026-06-02T12:00:00+00:00",
                    "last_error": "",
                    "selected_backend_ids": ["backend-a", "backend-b"],
                    "managed_port": 8320,
                    "current_proxy_url": "http://127.0.0.1:8318",
                    "stable_default_backend_id": "backend-a",
                    "selected_backend_snapshot": malformed_snapshot,
                }
                self.write_json_like(
                    self.state_path,
                    json.dumps(state_payload, sort_keys=True),
                )
                self.write_text(self.effective_mode_path, "stable\n")

                result = self.assess()

                self.assertEqual(
                    result.truth_slice_outcome,
                    state_startup_truth.TRUTH_SLICE_BLOCKED,
                )
                self.assertTrue(result.selected_backend_snapshot_present)
                self.registry_path.unlink()
                self.state_path.unlink()
                self.effective_mode_path.unlink()

    def test_selected_backend_snapshot_digest_mismatch_is_contradicted(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(
            self.state_path,
            self.state_payload(
                selected_backend_snapshot=self.selected_backend_snapshot(
                    selected_backends_digest="not-the-digest"
                )
            ),
        )
        self.write_text(self.effective_mode_path, "stable\n")

        result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONTRADICTED,
        )
        self.assertIn(
            "selected_backend_snapshot_digest",
            result.contradiction_fields,
        )

    def test_assessment_performs_no_writes_or_deletes(self) -> None:
        self.write_json_like(self.registry_path, self.registry_payload())
        self.write_json_like(self.state_path, self.state_payload())
        self.write_text(self.effective_mode_path, "stable\n")

        with (
            mock.patch.object(state_startup_truth.state_store, "write_json") as write_json,
            mock.patch.object(state_startup_truth.state_store, "write_text") as write_text,
            mock.patch.object(Path, "unlink") as unlink,
        ):
            result = self.assess()

        self.assertEqual(
            result.truth_slice_outcome,
            state_startup_truth.TRUTH_SLICE_CONSISTENT,
        )
        write_json.assert_not_called()
        write_text.assert_not_called()
        unlink.assert_not_called()

    def test_result_is_library_dataclass_not_packet_or_startup_verdict(self) -> None:
        result_fields = set(state_startup_truth.StartupTruthSliceAssessment.__dataclass_fields__)

        self.assertTrue(
            {
                "truth_slice_outcome",
                "machine_error_code",
                "reason",
                "registry_present",
                "supervisor_state_present",
                "effective_mode_artifact_present",
                "selected_backend_snapshot_present",
                "contradiction_fields",
            }.issubset(result_fields)
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
        self.assertTrue(forbidden.isdisjoint(result_fields))

    def test_module_does_not_import_runtime_cli_or_tooling_layers(self) -> None:
        source = Path(state_startup_truth.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {
            "wild_boar_proxy.runtime",
            "wild_boar_proxy.operator_surface",
            "wild_boar_proxy.cli",
            "wild_boar_proxy.web_design_live_server",
            "wild_boar_proxy.command_effects",
            "tools.truth_tree_harness",
        }
        self.assertTrue(forbidden.isdisjoint(imported_modules))


if __name__ == "__main__":
    unittest.main()
