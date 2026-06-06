# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest import mock

from tools.truth_tree_harness import (
    assert_declared_mutations_match,
    assert_no_truth_mutation,
    snapshot_truth_tree,
)
from wild_boar_proxy import runtime as runtime_mod
from wild_boar_proxy import runtime_repair


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


class HealthcheckProbeRepairContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.auth_dir = self.root / "auth"
        self.external_dir = self.managed_dir / "external-models"
        self.bin_dir = self.managed_dir / "bin"
        for path in (
            self.profile_dir,
            self.managed_dir,
            self.stable_dir,
            self.auth_dir,
            self.external_dir,
            self.bin_dir,
        ):
            path.mkdir(parents=True)

        self.stable_port = _free_port()
        stable_endpoint = f"http://127.0.0.1:{self.stable_port}/v1"
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "{stable_endpoint}"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n",
            encoding="utf-8",
        )
        (self.profile_dir / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": "test-healthcheck-probe-secret"}) + "\n",
            encoding="utf-8",
        )
        backend_auth = self.auth_dir / "backend-a.json"
        backend_auth.write_text("{}\n", encoding="utf-8")
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-06-01T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 0,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": str(backend_auth),
                            "fail_count": 0,
                            "success_count": 1,
                        }
                    ],
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "status": "healthy",
                    "effective_mode": "stable",
                    "stable_default_backend_id": "default-backend",
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": 9999,
                    "last_error": "",
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {self.stable_port}\n",
            encoding="utf-8",
        )
        self.launcher_script = self.managed_dir / "stable-runtime-launcher.sh"
        self.launcher_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.launcher_script.chmod(0o755)
        self.pid_file = self.managed_dir / "managed-proxy.pid"
        self.pid_file.write_text("999999\n", encoding="utf-8")
        self.paths = runtime_mod.RuntimePaths(
            profile_dir=self.profile_dir,
            managed_dir=self.managed_dir,
            stable_config=self.stable_dir / "config.yaml",
            auth_file=self.profile_dir / "auth.json",
            config_toml=self.profile_dir / "config.toml",
            runtime_mode_file=self.profile_dir / "runtime-mode.txt",
            runtime_effective_mode_file=self.profile_dir / "runtime-effective-mode.txt",
            registry_file=self.managed_dir / "backend-registry.json",
            state_file=self.managed_dir / "supervisor-state.json",
            managed_config_file=self.managed_dir / "managed-config.yaml",
            launcher_script=self.launcher_script,
            sync_script=self.managed_dir / "supervisor-sync.sh",
            accounts_bin=self.bin_dir / "codex-accounts",
            onboard_bin=self.bin_dir / "codex-account-onboard",
            lock_file=self.managed_dir / "wild-boar-proxy.lock",
            launcher_lock_file=self.managed_dir / "stable-runtime-launch.lock",
            repair_target_inventory_dir=self.managed_dir / "stable-repair-target",
            repair_target_reference_file=self.managed_dir / "approved-repair-target.json",
            target_switch_transaction_file=(
                self.managed_dir / "target-switch-transaction.json"
            ),
            stable_runtime_generated_config_file=(
                self.managed_dir / "stable-runtime-config.generated.yaml"
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_AUTH_FILE"] = str(self.profile_dir / "auth.json")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_RUNTIME_MODE_FILE"] = str(self.profile_dir / "runtime-mode.txt")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_REGISTRY_FILE"] = str(self.managed_dir / "backend-registry.json")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_LAUNCHER_SCRIPT"] = str(self.launcher_script)
        env["WBP_LOCK_FILE"] = str(self.managed_dir / "wild-boar-proxy.lock")
        env["WBP_LAUNCHER_LOCK_FILE"] = str(
            self.managed_dir / "stable-runtime-launch.lock"
        )
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def truth_snapshot(
        self, extra_paths: dict[str, Path] | None = None
    ) -> dict[str, dict[str, Any]]:
        paths = {
            "backend-registry.json": self.managed_dir / "backend-registry.json",
            "supervisor-state.json": self.managed_dir / "supervisor-state.json",
            "managed-config.yaml": self.managed_dir / "managed-config.yaml",
            "runtime-mode.txt": self.profile_dir / "runtime-mode.txt",
            "runtime-effective-mode.txt": (
                self.profile_dir / "runtime-effective-mode.txt"
            ),
            "config.toml": self.profile_dir / "config.toml",
            "managed-proxy.pid": self.pid_file,
        }
        if extra_paths is not None:
            paths.update(extra_paths)
        return snapshot_truth_tree(paths)

    def read_registry(self) -> dict[str, Any]:
        return json.loads((self.managed_dir / "backend-registry.json").read_text())

    def write_registry(self, payload: dict[str, Any]) -> None:
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(payload, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def read_state(self) -> dict[str, Any]:
        return json.loads((self.managed_dir / "supervisor-state.json").read_text())

    def write_state(self, payload: dict[str, Any]) -> None:
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(payload, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def prepare_managed_last_known_good_refresh_case(self) -> None:
        state = self.read_state()
        state["effective_mode"] = "managed"
        state["managed_port"] = 9999
        state["current_proxy_url"] = "http://127.0.0.1:10808"
        state.pop(runtime_mod.LAST_KNOWN_GOOD_PROXY_URL_FIELD, None)
        state.pop(runtime_mod.LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD, None)
        self.write_state(state)
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "managed\n",
            encoding="utf-8",
        )
        (self.profile_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:9999/v1"\n',
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )

    def run_managed_last_known_good_refresh_repair(self) -> dict[str, Any]:
        def fake_http_get_json(url: str, _api_key: str) -> dict[str, Any]:
            if url.endswith("/models"):
                return {"data": [{"id": "gpt-5.4"}]}
            if url.endswith(runtime_mod.RUNTIME_IDENTITY_ENDPOINT_PATH):
                state = self.read_state()
                return {
                    "schema_version": runtime_mod.RUNTIME_IDENTITY_SCHEMA_VERSION,
                    "runtime_marker": "test-managed-runtime",
                    "managed_config_identity": runtime_mod.get_managed_config_identity(
                        self.paths
                    ),
                    "selected_backends_digest": runtime_mod.get_selected_backends_digest(
                        state
                    ),
                    "runtime_version": "2",
                    "issued_for_endpoint": "http://127.0.0.1:9999/v1",
                }
            raise AssertionError(f"unexpected GET {url}")

        with (
            mock.patch.object(runtime_mod, "socket_is_listening", return_value=True),
            mock.patch.object(runtime_mod, "http_get_json", side_effect=fake_http_get_json),
            mock.patch.object(
                runtime_mod,
                "http_post_json",
                return_value={"output_text": "OK"},
            ),
            mock.patch.object(
                runtime_mod,
                "now_iso",
                return_value="2026-06-02T00:00:00+00:00",
            ),
        ):
            return runtime_mod.run_healthcheck_repair(self.paths)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def commit_rollback_eligible_transaction(
        self,
        *,
        transaction_id: str = "txn-rollback-command",
        mutation_id: str = "wbp-mut-rollback-command",
        before: bytes = b"old",
        after: bytes = b"new",
    ) -> Path:
        target = self.managed_dir / "rollback-target.json"
        target.write_bytes(before)
        runtime_mod.state_transaction.commit_state_transaction(
            self.managed_dir,
            transaction_id,
            (
                runtime_mod.state_transaction.TransactionWrite(
                    target_path=str(target),
                    payload=after,
                ),
            ),
            effect=runtime_mod.EFFECT_REPAIR,
            scope="rollback_command_test",
            mutation_id=mutation_id,
            rollback_eligible=True,
        )
        self.assertEqual(target.read_bytes(), after)
        return target

    def write_incomplete_transaction_metadata(
        self,
        transaction_id: str = "txn-incomplete-command",
    ) -> Path:
        metadata_path = runtime_mod.state_transaction.transaction_metadata_path(
            self.managed_dir / runtime_mod.state_transaction.TRANSACTION_STORE_DIRNAME,
            transaction_id,
        )
        runtime_mod.state_transaction.write_transaction_metadata(
            metadata_path,
            runtime_mod.state_transaction.TransactionMetadata(
                schema_version=runtime_mod.state_transaction.TRANSACTION_METADATA_SCHEMA_VERSION,
                transaction_id=transaction_id,
                state=runtime_mod.state_transaction.TRANSACTION_PREPARING,
                created_at_utc="2026-06-03T00:00:00+00:00",
                updated_at_utc="2026-06-03T00:00:01+00:00",
                transaction_root=str(self.managed_dir.resolve(strict=False)),
                files=(),
                error=None,
            ),
        )
        return metadata_path

    def test_healthcheck_probe_declares_probe_and_does_not_write_truth_files(self) -> None:
        before = self.truth_snapshot()
        result = self.run_cli("healthcheck", "--json")
        after = self.truth_snapshot()
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertNotEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertEqual(payload["attestation"]["attestation_source"], "healthcheck --json")
        self.assertEqual(
            payload["launch_readiness"]["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertEqual(
            payload["runtime_guardrails"]["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertNotIn("deterministic_stable_recovery_result", payload)
        self.assertNotIn("proxy_reprobe_adoption_result", payload)
        self.assertNotIn("mutation_id", payload)
        self.assertNotIn("mutation_ledger", payload)
        assert_no_truth_mutation(before, after)

    def test_healthcheck_probe_does_not_call_repair_primitives(self) -> None:
        with (
            mock.patch.object(
                runtime_mod,
                "clear_stale_managed_pid_if_needed",
                side_effect=AssertionError("probe must not clean stale pid"),
            ),
            mock.patch.object(
                runtime_mod,
                "reconcile_stable_fallback",
                side_effect=AssertionError("probe must not reconcile fallback"),
            ),
            mock.patch.object(
                runtime_mod,
                "refresh_last_known_good_proxy_from_healthcheck",
                side_effect=AssertionError("probe must not refresh last known good"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_stable_runtime_launcher_attempt",
                side_effect=AssertionError("probe must not launch repair"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_current_proxy_owner_path_activation",
                side_effect=AssertionError("probe must not adopt current proxy"),
            ),
            mock.patch.object(
                runtime_mod,
                "write_stable_runtime_consumer_snapshot",
                side_effect=AssertionError("probe must not write snapshots"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_startup_contract_repair_owner_path",
                side_effect=AssertionError("probe must not invoke startup contract repair"),
            ),
        ):
            payload = runtime_mod.run_healthcheck_probe(self.paths)

        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])

    def test_healthcheck_repair_declares_repair(self) -> None:
        result = self.run_cli("healthcheck", "--repair", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(
            payload["attestation"]["attestation_source"],
            "healthcheck --repair --json",
        )
        self.assertIsInstance(payload["changed_files"], list)
        self.assertIn("mutation_id", payload)
        self.assertIn("mutation_ledger", payload)
        self.assertEqual(payload["mutation_ledger"]["effect"], "repair")
        self.assertEqual(payload["mutation_ledger"]["scope"], "healthcheck_repair")
        self.assertFalse(payload["mutation_ledger"]["rollback_available"])
        self.assertIsNone(payload["mutation_ledger"]["rollback_id"])
        self.assertEqual(payload["mutation_ledger"]["rollback_phase"], "ledger_only")

    def test_healthcheck_repair_without_mutation_reports_not_mutated_ledger(self) -> None:
        self.pid_file.unlink()

        payload = runtime_mod.run_healthcheck(
            self.paths,
            allow_recovery=False,
            allow_last_known_good_proxy_write=False,
            allow_current_proxy_auto_adoption=False,
            allow_stable_fallback_write=False,
            allow_stale_pid_cleanup=False,
            effect=runtime_mod.EFFECT_REPAIR,
        )

        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], [])
        self.assertIsNone(payload["mutation_id"])
        self.assertEqual(payload["mutation_ledger"]["status"], "not_mutated")
        self.assertEqual(payload["mutation_ledger"]["changed_files"], [])
        self.assertFalse(payload["mutation_ledger"]["rollback_available"])
        self.assertIsNone(payload["mutation_ledger"]["rollback_id"])

    def test_healthcheck_repair_attempts_stable_activation_for_auth_gap(
        self,
    ) -> None:
        state = json.loads(self.paths.state_file.read_text(encoding="utf-8"))
        state["selected_backend_ids"] = []
        state["selected_backend_snapshot"] = runtime_mod.build_selected_backend_snapshot_payload(
            selected_backend_ids=["backend-a"],
            observed_at_utc="2026-06-01T00:00:00+00:00",
            source_class="supervisor_owner_observed",
            source_name="sync --json",
            source_run_id="sync:2026-06-01T00:00:00+00:00",
            producer_version="2",
        )
        self.paths.state_file.write_text(json.dumps(state) + "\n", encoding="utf-8")
        auth_error = urllib.error.HTTPError(
            url="http://127.0.0.1:8318/v1/responses",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(
                b'{"error":{"message":"auth_unavailable: no auth available"}}'
            ),
        )
        process_result = {
            "status": "ok",
            "machine_error_code": runtime_mod.PROCESS_OK,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
            "timed_out": False,
            "duration_seconds": 0.0,
        }
        launch_attempt = runtime_mod.StableRuntimeLaunchAttempt(
            desired_kind="approved_repair_target",
            observed_path=self.auth_dir,
            activation_attempted=True,
            generated_config_regenerated=True,
            activation_method="process_local_env_override",
            selected_config_file=str(self.paths.stable_runtime_generated_config_file),
            selected_source_kind="approved_repair_target",
            selected_source_path=str(self.paths.repair_target_inventory_dir),
            launcher_exit_code=0,
            stdout="",
            stderr="",
            process_result=process_result,
        )

        with (
            mock.patch.object(runtime_mod, "socket_is_listening", return_value=True),
            mock.patch.object(
                runtime_mod,
                "http_get_json",
                return_value={"data": [{"id": "gpt-5.4"}]},
            ),
            mock.patch.object(
                runtime_mod,
                "http_post_json",
                side_effect=[auth_error, {"output_text": "OK"}],
            ),
            mock.patch.object(
                runtime_mod,
                "run_stable_runtime_launcher_attempt",
                return_value=launch_attempt,
            ) as launcher,
        ):
            payload = runtime_mod.run_healthcheck(
                self.paths,
                effect=runtime_mod.EFFECT_REPAIR,
            )

        launcher.assert_called_once()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        recovery = payload["deterministic_stable_recovery_result"]
        self.assertTrue(recovery["attempted"])
        self.assertEqual(recovery["entry_lane"], "explicit_stable_recovery_lane")
        self.assertEqual(recovery["outcome"], "approved_target_recovered")
        self.assertTrue(recovery["live_runtime_observation_confirmed"])
        self.assertEqual(
            recovery["confirmation_basis"],
            "approved_target_activation_plus_live_runtime_observation",
        )

    def test_healthcheck_repair_temp_cleanup_ledger_reports_file_delete(self) -> None:
        self.pid_file.unlink()
        stale = self.managed_dir / ".wbp-tmp-state.json"
        stale.write_text("old\n", encoding="utf-8")
        os.utime(stale, (1, 1))

        before = self.truth_snapshot({"stale-temp": stale})
        payload = runtime_mod.run_healthcheck(
            self.paths,
            allow_recovery=False,
            allow_last_known_good_proxy_write=False,
            allow_current_proxy_auto_adoption=False,
            allow_stable_fallback_write=False,
            allow_stale_pid_cleanup=False,
            effect=runtime_mod.EFFECT_REPAIR,
        )
        after = self.truth_snapshot({"stale-temp": stale})

        self.assertIn(str(stale), payload["changed_files"])
        assert_declared_mutations_match(before, after, payload["changed_files"])
        self.assertRegex(payload["mutation_id"], r"^wbp-mut-[0-9a-f]{20}$")
        ledger = payload["mutation_ledger"]
        self.assertEqual(ledger["status"], "mutated")
        records = {
            record["path"]: record
            for record in ledger["changed_files"]
        }
        self.assertEqual(set(records), set(payload["changed_files"]))
        record = records[str(stale)]
        self.assertEqual(record["operation"], "delete")
        self.assertEqual(record["before_kind"], "file")
        self.assertEqual(record["after_kind"], "missing")
        self.assertIsInstance(record["before_sha256"], str)
        self.assertIsNone(record["after_sha256"])
        self.assertFalse(stale.exists())

    def test_healthcheck_repair_ledger_covers_every_top_level_changed_file(self) -> None:
        payload = runtime_mod.run_healthcheck_repair(self.paths)

        self.assertEqual(payload["effect"], "repair")
        ledger = payload["mutation_ledger"]
        self.assertEqual(
            {record["path"] for record in ledger["changed_files"]},
            set(payload["changed_files"]),
        )
        if payload["changed_files"]:
            self.assertRegex(payload["mutation_id"], r"^wbp-mut-[0-9a-f]{20}$")
            self.assertEqual(ledger["status"], "mutated")
        else:
            self.assertIsNone(payload["mutation_id"])
            self.assertEqual(ledger["status"], "not_mutated")

    def test_healthcheck_repair_wrapper_requires_mutation_metadata(self) -> None:
        class MissingMetadataDependencies:
            def run_healthcheck(self, *_args, **_kwargs):
                return {
                    "status": "ok",
                    "effect": "repair",
                    "changed_files": [],
                    "mutation_id": None,
                }

        with self.assertRaisesRegex(RuntimeError, "mutation_ledger"):
            runtime_repair.run_healthcheck_repair(
                self.paths,
                dependencies=MissingMetadataDependencies(),
            )

        class CompleteMetadataDependencies:
            def run_healthcheck(self, *_args, **_kwargs):
                return {
                    "status": "ok",
                    "effect": "repair",
                    "changed_files": [],
                    "mutation_id": None,
                    "mutation_ledger": {
                        "status": "not_mutated",
                        "changed_files": [],
                    },
                }

        payload = runtime_repair.run_healthcheck_repair(
            self.paths,
            dependencies=CompleteMetadataDependencies(),
        )
        self.assertIn("mutation_id", payload)
        self.assertIn("mutation_ledger", payload)

    def test_healthcheck_repair_last_known_good_refresh_is_rollback_backed(
        self,
    ) -> None:
        self.pid_file.unlink()
        self.prepare_managed_last_known_good_refresh_case()

        payload = self.run_managed_last_known_good_refresh_repair()

        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["changed_files"], [str(self.paths.state_file)])
        self.assertRegex(payload["mutation_id"], r"^wbp-mut-[0-9a-f]{20}$")
        ledger = payload["mutation_ledger"]
        self.assertEqual(
            ledger["scope"],
            runtime_mod.HEALTHCHECK_LAST_KNOWN_GOOD_PROXY_REFRESH_SCOPE,
        )
        self.assertTrue(ledger["rollback_available"])
        self.assertRegex(ledger["rollback_id"], r"^wbp-rb-[0-9a-f]{20}$")
        self.assertEqual(ledger["rollback_phase"], "last_transaction")
        self.assertRegex(ledger["transaction_id"], r"^healthcheck-lkg-[0-9a-f]{20}$")
        artifact_paths = {
            record["path"] for record in ledger["transaction_store_artifacts"]
        }
        self.assertTrue(
            any(path.endswith(".transaction.json") for path in artifact_paths)
        )
        self.assertTrue(any(path.endswith(".files") for path in artifact_paths))
        self.assertTrue(artifact_paths.isdisjoint(set(payload["changed_files"])))

        metadata_path = Path(
            next(path for path in artifact_paths if path.endswith(".transaction.json"))
        )
        metadata = runtime_mod.state_transaction.read_transaction_metadata(metadata_path)
        self.assertEqual(metadata.mutation_id, payload["mutation_id"])
        self.assertEqual(metadata.rollback_id, ledger["rollback_id"])
        self.assertEqual(metadata.scope, ledger["scope"])
        self.assertTrue(metadata.rollback_eligible)
        state = self.read_state()
        self.assertEqual(
            state[runtime_mod.LAST_KNOWN_GOOD_PROXY_URL_FIELD],
            "http://127.0.0.1:10808",
        )

        rollback = runtime_mod.state_transaction.rollback_latest_state_transaction(
            self.managed_dir
        )

        self.assertTrue(rollback.rollback_available)
        self.assertEqual(
            rollback.machine_error_code,
            runtime_mod.state_transaction.STATE_TRANSACTION_ROLLBACK_COMPLETED,
        )
        self.assertEqual(rollback.rollback_id, ledger["rollback_id"])
        self.assertEqual(
            rollback.changed_files,
            (str(self.paths.state_file.resolve(strict=False)),),
        )
        rolled_back_state = self.read_state()
        self.assertNotIn(
            runtime_mod.LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            rolled_back_state,
        )

    def test_rollback_latest_dry_run_reports_ready_without_writes(self) -> None:
        target = self.commit_rollback_eligible_transaction()
        metadata_path = next((self.managed_dir / "transactions").glob("*.transaction.json"))
        before_metadata = metadata_path.read_text(encoding="utf-8")

        result = self.run_cli("rollback", "--latest", "--dry-run", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertTrue(payload["rollback_available"])
        self.assertEqual(payload["rollback_status"], "rollback_ready")
        self.assertEqual(payload["would_change_files"], [str(target.resolve(strict=False))])
        self.assertEqual(target.read_bytes(), b"new")
        self.assertEqual(metadata_path.read_text(encoding="utf-8"), before_metadata)

    def test_rollback_latest_dry_run_no_eligible_does_not_false_green(self) -> None:
        result = self.run_cli("rollback", "--latest", "--dry-run", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertNotEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(payload["rollback_available"])
        self.assertEqual(payload["rollback_status"], "rollback_not_available")

    def test_rollback_latest_apply_restores_file_and_verifies(self) -> None:
        target = self.commit_rollback_eligible_transaction()

        result = self.run_cli("rollback", "--latest", "--apply", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], [str(target.resolve(strict=False))])
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_transaction.STATE_TRANSACTION_ROLLBACK_COMPLETED,
        )
        self.assertTrue(payload["post_rollback_verification"]["verified"])
        self.assertEqual(target.read_bytes(), b"old")

    def test_rollback_latest_apply_blocks_second_attempt_without_false_green(self) -> None:
        target = self.commit_rollback_eligible_transaction()
        first = self.run_cli("rollback", "--latest", "--apply", "--json")
        first_payload = _strict_json_object(first.stdout)
        self.assertEqual(first_payload["status"], "ok")

        second = self.run_cli("rollback", "--latest", "--apply", "--json")
        second_payload = _strict_json_object(second.stdout)

        self.assertEqual(second.stderr, "")
        self.assertEqual(second.returncode, second_payload["exit_code"])
        self.assertNotEqual(second_payload["status"], "ok")
        self.assertEqual(second_payload["changed_files"], [])
        self.assertFalse(second_payload["rollback_available"])
        self.assertEqual(second_payload["rollback_status"], "rollback_not_available")
        self.assertEqual(second_payload["rollback_blocked_reasons"], [])
        self.assertEqual(target.read_bytes(), b"old")

    def test_rollback_latest_apply_blocks_drift_before_writes(self) -> None:
        target = self.commit_rollback_eligible_transaction()
        target.write_bytes(b"drift")

        result = self.run_cli("rollback", "--latest", "--apply", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertNotEqual(payload["status"], "ok")
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(payload["rollback_available"])
        self.assertIn("target_sha256_drift", " ".join(payload["rollback_blocked_reasons"]))
        self.assertEqual(target.read_bytes(), b"drift")

    def test_rollback_latest_apply_blocks_missing_backup_before_writes(self) -> None:
        target = self.commit_rollback_eligible_transaction()
        metadata_path = next((self.managed_dir / "transactions").glob("*.transaction.json"))
        metadata = runtime_mod.state_transaction.read_transaction_metadata(metadata_path)
        Path(metadata.files[0].backup_path).unlink()

        result = self.run_cli("rollback", "--latest", "--apply", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertNotEqual(payload["status"], "ok")
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(payload["rollback_available"])
        self.assertIn(
            "backup_not_regular_file",
            " ".join(payload["rollback_blocked_reasons"]),
        )
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_latest_apply_blocks_dirty_store_before_writes(self) -> None:
        target = self.commit_rollback_eligible_transaction()
        self.write_incomplete_transaction_metadata()

        result = self.run_cli("rollback", "--latest", "--apply", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertNotEqual(payload["status"], "ok")
        self.assertEqual(payload["changed_files"], [])
        self.assertFalse(payload["rollback_available"])
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_transaction.STATE_TRANSACTION_INCOMPLETE,
        )
        self.assertEqual(payload["rollback_blocked_reasons"], ["transaction_store_incomplete"])
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_latest_apply_failed_post_verify_does_not_false_green(
        self,
    ) -> None:
        target = self.commit_rollback_eligible_transaction()

        with mock.patch.object(
            runtime_mod,
            "_verify_latest_rollback_result",
            return_value={
                "status": "failed",
                "verified": False,
                "files": [
                    {
                        "target_path": str(target.resolve(strict=False)),
                        "expected_kind": "file",
                        "observed_kind": "file",
                        "expected_sha256": "expected",
                        "observed_sha256": "observed",
                        "verified": False,
                    }
                ],
            },
        ):
            payload = runtime_mod.run_rollback_latest_apply(self.paths)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(
            payload["machine_error_code"],
            "STATE_TRANSACTION_ROLLBACK_POST_VERIFY_FAILED",
        )
        self.assertEqual(payload["changed_files"], [str(target.resolve(strict=False))])
        self.assertFalse(payload["post_rollback_verification"]["verified"])
        self.assertEqual(target.read_bytes(), b"old")

    def test_rollback_latest_apply_exception_after_write_reports_changed_files(
        self,
    ) -> None:
        target = self.commit_rollback_eligible_transaction()

        def partial_rollback(*_args: Any, **_kwargs: Any) -> object:
            target.write_bytes(b"old")
            raise runtime_mod.state_transaction.StateTransactionError(
                "Rollback failed after writing target.",
                machine_error_code=(
                    runtime_mod.state_transaction.STATE_TRANSACTION_FAILED_BLOCKED
                ),
            )

        with mock.patch.object(
            runtime_mod.state_transaction,
            "rollback_latest_state_transaction",
            side_effect=partial_rollback,
        ):
            payload = runtime_mod.run_rollback_latest_apply(self.paths)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_transaction.STATE_TRANSACTION_FAILED_BLOCKED,
        )
        self.assertEqual(payload["changed_files"], [str(target.resolve(strict=False))])
        self.assertEqual(target.read_bytes(), b"old")

    def test_rollback_latest_apply_exception_before_write_keeps_changed_files_empty(
        self,
    ) -> None:
        target = self.commit_rollback_eligible_transaction()

        def blocked_rollback(*_args: Any, **_kwargs: Any) -> object:
            raise runtime_mod.state_transaction.StateTransactionError(
                "Rollback failed before writing target.",
                machine_error_code=(
                    runtime_mod.state_transaction.STATE_TRANSACTION_FAILED_BLOCKED
                ),
            )

        with mock.patch.object(
            runtime_mod.state_transaction,
            "rollback_latest_state_transaction",
            side_effect=blocked_rollback,
        ):
            payload = runtime_mod.run_rollback_latest_apply(self.paths)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(target.read_bytes(), b"new")

    def test_rollback_latest_cli_rejects_mutation_id_selection(self) -> None:
        target = self.commit_rollback_eligible_transaction()

        result = self.run_cli(
            "rollback",
            "--latest",
            "--mutation-id",
            "wbp-mut-forbidden",
            "--dry-run",
            "--json",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("unrecognized arguments", result.stderr)
        self.assertEqual(target.read_bytes(), b"new")

    def test_status_and_healthcheck_do_not_use_rollback_surface(self) -> None:
        def forbidden(_transaction_root: Path) -> object:
            raise AssertionError("status/healthcheck must not call rollback")

        with (
            mock.patch.object(
                runtime_mod.state_transaction,
                "preflight_latest_state_transaction_rollback",
                side_effect=forbidden,
            ),
            mock.patch.object(
                runtime_mod.state_transaction,
                "rollback_latest_state_transaction",
                side_effect=forbidden,
            ),
        ):
            status_payload = runtime_mod.summarize_status(self.paths)
            health_payload = runtime_mod.run_healthcheck_probe(self.paths)

        self.assertEqual(status_payload["effect"], "read")
        self.assertEqual(health_payload["effect"], "probe")

    def test_healthcheck_repair_mixed_writes_do_not_claim_rollback_available(
        self,
    ) -> None:
        self.prepare_managed_last_known_good_refresh_case()

        payload = self.run_managed_last_known_good_refresh_repair()

        self.assertIn(str(self.paths.state_file), payload["changed_files"])
        self.assertIn(str(self.pid_file), payload["changed_files"])
        ledger = payload["mutation_ledger"]
        self.assertFalse(ledger["rollback_available"])
        self.assertIsNone(ledger["rollback_id"])
        self.assertEqual(ledger["rollback_phase"], "ledger_only")
        self.assertEqual(ledger["scope"], "healthcheck_repair")
        self.assertNotIn("transaction_id", ledger)
        self.assertIn("transaction_store_artifacts", ledger)
        self.assertEqual(
            {record["path"] for record in ledger["changed_files"]},
            set(payload["changed_files"]),
        )

    def test_healthcheck_repair_mutation_candidates_include_transaction_artifacts(
        self,
    ) -> None:
        store = self.managed_dir / runtime_mod.state_transaction.TRANSACTION_STORE_DIRNAME
        metadata_path = store / "txn-candidate.transaction.json"
        work_root = store / "txn-candidate.files"
        metadata_path.parent.mkdir(parents=True)
        metadata_path.write_text("{}\n", encoding="utf-8")
        work_root.mkdir()

        candidates = runtime_mod.healthcheck_repair_mutation_surface_candidates(
            self.paths
        )

        self.assertIn(metadata_path, candidates)
        self.assertIn(work_root, candidates)

    def test_runtime_startup_lock_recovery_preserves_same_source_lock_path(self) -> None:
        captured: dict[str, Any] = {}
        real = runtime_mod.state_startup_lock.run_startup_lock_slice_recovery

        def capture(*args: Any, **kwargs: Any) -> Any:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return real(*args, **kwargs)

        with runtime_mod.lock_file_owner_path(self.paths.lock_file):
            with mock.patch.object(
                runtime_mod.state_startup_lock,
                "run_startup_lock_slice_recovery",
                side_effect=capture,
            ):
                result = runtime_mod.run_runtime_startup_lock_slice_recovery(self.paths)

        self.assertEqual(
            result.lock_slice_recovery_outcome,
            runtime_mod.state_startup_lock.LOCK_SLICE_RECOVERY_CLEAN,
        )
        self.assertIsNotNone(result.assessment)
        self.assertEqual(
            result.assessment.lock_slice_outcome,
            runtime_mod.state_startup_lock.LOCK_SLICE_CLEAR,
        )
        self.assertEqual(captured["args"][0], self.paths.lock_file)
        self.assertEqual(
            captured["kwargs"]["assessment_source_lock_path"],
            self.paths.lock_file,
        )
        self.assertIsNotNone(captured["args"][1])
        self.assertIsNotNone(captured["args"][2])

    def test_startup_contract_owner_path_reports_temp_cleanup_changed_files(self) -> None:
        stale = self.managed_dir / ".wbp-tmp-state.json"
        stale.write_text("old\n", encoding="utf-8")
        os.utime(stale, (1, 1))

        result = runtime_mod.run_startup_contract_repair_owner_path(self.paths)

        self.assertEqual(
            result.core_result.startup_contract_outcome,
            runtime_mod.state_startup_contract.STARTUP_CONTRACT_AUTO_RECOVERED,
        )
        self.assertEqual(
            result.core_result.temp_recovery.temp_recovery_outcome,
            runtime_mod.state_startup_recovery.TEMP_RECOVERY_RECOVERED,
        )
        self.assertIn(str(stale), result.changed_files)
        self.assertFalse(stale.exists())

    def test_startup_contract_owner_path_reports_legacy_lock_cleanup_changed_files(self) -> None:
        self.paths.lock_file.write_text("999999\n", encoding="utf-8")

        result = runtime_mod.run_startup_contract_repair_owner_path(self.paths)

        self.assertEqual(
            result.core_result.startup_contract_outcome,
            runtime_mod.state_startup_contract.STARTUP_CONTRACT_AUTO_RECOVERED,
        )
        self.assertEqual(
            result.core_result.lock_recovery.lock_slice_recovery_outcome,
            runtime_mod.state_startup_lock.LOCK_SLICE_RECOVERY_RECOVERED,
        )
        self.assertIn(str(self.paths.lock_file), result.changed_files)
        self.assertFalse(self.paths.lock_file.exists())

    def test_healthcheck_repair_exposes_separate_startup_contract_owner_surface(self) -> None:
        payload = runtime_mod.run_healthcheck_repair(self.paths)

        self.assertEqual(payload["effect"], "repair")
        self.assertIn("startup_contract_repair_contract", payload)
        self.assertIn("startup_contract_repair_result", payload)
        self.assertEqual(
            payload["startup_contract_repair_contract"]["owner_command_surface"],
            "healthcheck --repair --json",
        )
        self.assertEqual(
            payload["startup_contract_repair_result"]["owner_command_surface"],
            "healthcheck --repair --json",
        )
        self.assertEqual(payload["startup_contract_repair_result"]["status"], "completed")
        self.assertEqual(
            payload["startup_contract_repair_result"]["startup_contract_outcome"],
            runtime_mod.state_startup_contract.STARTUP_CONTRACT_CLEAN,
        )
        self.assertFalse(
            payload["startup_contract_repair_result"]["live_runtime_observation_confirmed"]
        )
        self.assertFalse(payload["startup_contract_repair_result"]["effectful_claim_allowed"])
        self.assertEqual(
            payload["startup_contract_repair_result"]["guardrail_status"],
            "observation_only",
        )
        if "deterministic_stable_recovery_result" in payload:
            self.assertNotIn(
                "startup_contract_outcome",
                payload["deterministic_stable_recovery_result"],
            )
        self.assertNotIn("entry_lane", payload["startup_contract_repair_result"])

    def test_summarize_status_does_not_expose_startup_contract_repair_surface(self) -> None:
        health_payload = runtime_mod.run_healthcheck_repair(self.paths)

        status_payload = runtime_mod.summarize_status(self.paths, health_payload=health_payload)

        self.assertNotIn("startup_contract_repair_contract", status_payload)
        self.assertNotIn("startup_contract_repair_result", status_payload)
        self.assertNotIn(
            "startup_contract_repair_contract",
            status_payload["stable_runtime_consumer"],
        )
        self.assertNotIn(
            "startup_contract_repair_result",
            status_payload["stable_runtime_consumer"],
        )
        self.assertEqual(
            status_payload["runtime_guardrails"]["owner_command_surface"],
            "status --json",
        )

    def test_healthcheck_repair_truth_contradiction_blocks_without_false_green(self) -> None:
        state = self.read_state()
        state["stable_default_backend_id"] = "other-backend"
        self.write_state(state)

        payload = runtime_mod.run_healthcheck_repair(self.paths)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_startup_contract.STATE_STARTUP_CONTRACT_BLOCKED,
        )
        self.assertEqual(payload["runtime_guardrails"]["status"], "blocked")
        self.assertIn(
            "startup_contract_blocked",
            payload["runtime_guardrails"]["failed_checks"],
        )
        self.assertEqual(payload["startup_contract_repair_result"]["status"], "blocked")
        self.assertIn(
            runtime_mod.state_startup_truth.TRUTH_SLICE_CONTRADICTED,
            payload["startup_contract_repair_result"]["blocking_reasons"],
        )
        self.assertFalse(payload["startup_contract_repair_result"]["effectful_claim_allowed"])

    def test_healthcheck_repair_schema_blocked_stays_non_green(self) -> None:
        state = self.read_state()
        state["schema_version"] = 99
        self.write_state(state)

        payload = runtime_mod.run_healthcheck_repair(self.paths)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_startup_contract.STATE_STARTUP_CONTRACT_BLOCKED,
        )
        self.assertEqual(payload["startup_contract_repair_result"]["status"], "blocked")
        self.assertIn(
            runtime_mod.state_startup_schema.SCHEMA_SLICE_BLOCKED,
            payload["startup_contract_repair_result"]["blocking_reasons"],
        )
        self.assertEqual(payload["startup_contract_repair_result"]["guardrail_status"], "blocked")

    def test_healthcheck_repair_dirty_transaction_blocks_before_runtime_writes(
        self,
    ) -> None:
        metadata_path = self.write_incomplete_transaction_metadata()
        before = self.truth_snapshot({"transaction-metadata": metadata_path})

        payload = runtime_mod.run_healthcheck_repair(self.paths)

        after = self.truth_snapshot({"transaction-metadata": metadata_path})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_startup_contract.STATE_STARTUP_CONTRACT_BLOCKED,
        )
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], [])
        self.assertIsNone(payload["mutation_id"])
        self.assertEqual(payload["mutation_ledger"]["status"], "not_mutated")
        self.assertEqual(payload["runtime_guardrails"]["status"], "blocked")
        self.assertIn(
            "startup_contract_blocked",
            payload["runtime_guardrails"]["failed_checks"],
        )
        startup_result = payload["startup_contract_repair_result"]
        self.assertEqual(startup_result["status"], "blocked")
        self.assertEqual(
            startup_result["temp_recovery_outcome"],
            runtime_mod.state_startup_recovery.TEMP_RECOVERY_BLOCKED,
        )
        self.assertIn(
            runtime_mod.state_startup_recovery.REASON_TRANSACTION_INCOMPLETE,
            startup_result["blocking_reasons"],
        )
        self.assertFalse(startup_result["effectful_claim_allowed"])
        self.assertTrue(self.pid_file.exists())
        assert_no_truth_mutation(before, after)

    def test_healthcheck_repair_blocked_lock_blocks_before_runtime_writes(
        self,
    ) -> None:
        self.paths.lock_file.write_text("{not-json\n", encoding="utf-8")
        before = self.truth_snapshot({"runtime-lock": self.paths.lock_file})

        payload = runtime_mod.run_healthcheck_repair(self.paths)

        after = self.truth_snapshot({"runtime-lock": self.paths.lock_file})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            runtime_mod.state_startup_contract.STATE_STARTUP_CONTRACT_BLOCKED,
        )
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(payload["changed_files"], [])
        self.assertIsNone(payload["mutation_id"])
        self.assertEqual(payload["mutation_ledger"]["status"], "not_mutated")
        startup_result = payload["startup_contract_repair_result"]
        self.assertEqual(startup_result["status"], "blocked")
        self.assertEqual(
            startup_result["lock_slice_recovery_outcome"],
            runtime_mod.state_startup_lock.LOCK_SLICE_RECOVERY_BLOCKED,
        )
        self.assertFalse(startup_result["effectful_claim_allowed"])
        self.assertTrue(self.paths.lock_file.exists())
        self.assertTrue(self.pid_file.exists())
        assert_no_truth_mutation(before, after)

    def test_lock_file_owner_path_materializes_structured_lock_carrier(self) -> None:
        lock_file = self.managed_dir / "wild-boar-proxy.lock"

        with runtime_mod.lock_file_owner_path(lock_file):
            payload = json.loads(lock_file.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["schema_version"],
            runtime_mod.RUNTIME_LOCK_CARRIER_SCHEMA_VERSION,
        )
        self.assertEqual(payload["carrier_kind"], runtime_mod.RUNTIME_LOCK_CARRIER_KIND)
        self.assertEqual(payload["pid"], os.getpid())
        self.assertEqual(payload["uid"], os.getuid())
        self.assertEqual(payload["hostname"], socket.gethostname())
        self.assertIsInstance(payload["process_create_time"], (int, float))
        self.assertIsInstance(payload["started_at_utc"], str)
        self.assertTrue(payload["started_at_utc"])
        self.assertIsInstance(payload["command"], str)
        self.assertTrue(payload["command"])
        self.assertFalse(lock_file.exists())

    def test_lock_file_owner_path_degrades_when_process_probe_tool_is_missing(
        self,
    ) -> None:
        lock_file = self.managed_dir / "wild-boar-proxy.lock"

        with mock.patch.object(runtime_mod.shutil, "which", return_value=None):
            with mock.patch.object(
                runtime_mod.subprocess,
                "run",
                side_effect=AssertionError("metadata probe must not use subprocess.run"),
            ):
                with runtime_mod.lock_file_owner_path(lock_file):
                    raw_payload = lock_file.read_text(encoding="utf-8")

        self.assertEqual(raw_payload, f"{os.getpid()}\n")
        self.assertFalse(lock_file.exists())


if __name__ == "__main__":
    unittest.main()
