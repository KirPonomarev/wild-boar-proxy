# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from wild_boar_proxy import runtime


class RuntimeNativeAuthRecoveryTests(unittest.TestCase):
    def test_auth_pool_hygiene_uses_snapshot_as_observed_selection_when_runtime_loaded_ids_empty(
        self,
    ) -> None:
        registry = {
            "backends": [
                {
                    "id": "backend-a",
                    "pool": "active",
                    "status": "healthy",
                    "enabled": True,
                    "auth_ref": "/tmp/backend-a.json",
                    "priority": 10,
                    "fail_count": 0,
                    "success_count": 1,
                },
                {
                    "id": "backend-b",
                    "pool": "active",
                    "status": "healthy",
                    "enabled": True,
                    "auth_ref": "/tmp/backend-b.json",
                    "priority": 20,
                    "fail_count": 0,
                    "success_count": 1,
                },
            ]
        }
        snapshot = runtime.build_selected_backend_snapshot_payload(
            selected_backend_ids=["backend-a", "backend-b"],
            observed_at_utc="2026-05-29T00:00:00+00:00",
            source_class="supervisor_owner_observed",
            source_name="sync --json",
            source_run_id="sync:2026-05-29T00:00:00+00:00",
            producer_version="2",
        )
        state = {
            "selected_backend_ids": [],
            "selected_backend_snapshot": snapshot,
        }

        with unittest.mock.patch("wild_boar_proxy.runtime.now_iso", return_value="2026-05-29T00:00:30+00:00"):
            hygiene = runtime.summarize_auth_pool_hygiene(registry, state)

        self.assertEqual(
            hygiene["selected_backend_ids_observed"],
            ["backend-a", "backend-b"],
        )
        self.assertEqual(hygiene["selected_backend_ids_runtime_loaded"], [])
        self.assertEqual(
            hygiene["selected_backend_observation_source"],
            "runtime_state.selected_backend_snapshot",
        )
        self.assertEqual(hygiene["selected_backend_runtime_loaded_count"], 0)
        self.assertEqual(hygiene["selected_launch_capable_backend_count"], 2)

    def test_native_auth_recovery_hint_requires_owner_action_after_selected_backend_observation(
        self,
    ) -> None:
        hint = runtime.build_native_auth_recovery_hint(
            machine_error_code="AUTH_UNAVAILABLE",
            auth_pool_hygiene={
                "launch_capable_backend_count": 15,
                "selected_backend_ids_observed": ["backend-a"],
                "selected_backend_ids_runtime_loaded": [],
                "selected_backend_observation_source": "runtime_state.selected_backend_snapshot",
            },
        )

        self.assertEqual(hint["status"], "owner_action_required")
        self.assertTrue(hint["owner_action_required"])
        self.assertEqual(hint["next_action"], "accounts_login_start")
        self.assertEqual(
            hint["command_surface"],
            "accounts login start --provider codex --mode device --json",
        )
        self.assertTrue(hint["selection_gap_detected"])

    def test_native_auth_recovery_hint_recommends_sync_without_selected_backend_observation(
        self,
    ) -> None:
        hint = runtime.build_native_auth_recovery_hint(
            machine_error_code="AUTH_UNAVAILABLE",
            auth_pool_hygiene={
                "launch_capable_backend_count": 3,
                "selected_backend_ids_observed": [],
                "selected_backend_ids_runtime_loaded": [],
                "selected_backend_observation_source": "",
            },
        )

        self.assertEqual(hint["status"], "sync_recommended")
        self.assertFalse(hint["owner_action_required"])
        self.assertEqual(hint["next_action"], "sync")
        self.assertEqual(hint["command_surface"], "sync --json")

    def test_owner_login_inventory_scope_allows_stable_config_parent(self) -> None:
        paths = runtime.RuntimePaths(
            profile_dir=Path("/tmp/wbp-profile"),
            managed_dir=Path("/tmp/wbp-profile/managed"),
            stable_config=Path("/tmp/stable-engine/config.yaml"),
            auth_file=Path("/tmp/wbp-profile/auth.json"),
            config_toml=Path("/tmp/wbp-profile/config.toml"),
            runtime_mode_file=Path("/tmp/wbp-profile/runtime-mode.txt"),
            runtime_effective_mode_file=Path("/tmp/wbp-profile/runtime-effective-mode.txt"),
            registry_file=Path("/tmp/wbp-profile/managed/backend-registry.json"),
            state_file=Path("/tmp/wbp-profile/managed/supervisor-state.json"),
            managed_config_file=Path("/tmp/wbp-profile/managed/managed-config.yaml"),
            launcher_script=Path("/tmp/wbp-profile/codex-custom-launch.sh"),
            sync_script=Path("/tmp/wbp-profile/managed/supervisor-sync.sh"),
            accounts_bin=Path("/tmp/wbp-profile/managed/bin/codex-accounts"),
            onboard_bin=Path("/tmp/wbp-profile/managed/bin/codex-account-onboard"),
            lock_file=Path("/tmp/wbp-profile/managed/wild-boar-proxy.lock"),
            launcher_lock_file=Path("/tmp/wbp-profile/managed/stable-runtime-launch.lock"),
            repair_target_inventory_dir=Path("/tmp/wbp-profile/managed/stable-repair-target"),
            repair_target_reference_file=Path("/tmp/wbp-profile/managed/approved-repair-target.json"),
            target_switch_transaction_file=Path("/tmp/wbp-profile/managed/target-switch-transaction.json"),
            stable_runtime_generated_config_file=Path("/tmp/wbp-profile/managed/stable-runtime-config.generated.yaml"),
        )

        self.assertTrue(
            runtime.path_is_admitted_owner_login_inventory_path(
                paths, Path("/tmp/stable-engine")
            )
        )
        self.assertTrue(
            runtime.path_is_admitted_owner_login_inventory_path(
                paths, Path("/tmp/stable-engine/device-login")
            )
        )
        self.assertFalse(
            runtime.path_is_admitted_owner_login_inventory_path(
                paths, Path("/tmp/unrelated-auth-root")
            )
        )

    def test_find_login_auth_candidates_detects_changed_existing_auth_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            auth_dir = root / "auth-dir"
            auth_dir.mkdir(parents=True, exist_ok=True)
            auth_path = auth_dir / "codex-kir.test.gpt26@gmail.com-team.json"
            auth_path.write_text('{"email":"kir.test.gpt26@gmail.com","version":1}\n', encoding="utf-8")
            paths = runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=auth_dir / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir / "stable-runtime-config.generated.yaml",
            )
            before_entries = [
                str(auth_path.expanduser().resolve(strict=False)),
            ]
            before_metadata = {
                str(auth_path.expanduser().resolve(strict=False)): runtime.login_auth_inventory_entry_metadata(
                    auth_path
                )
            }

            auth_path.write_text('{"email":"kir.test.gpt26@gmail.com","version":2}\n', encoding="utf-8")

            with unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_auth_inventory_dir",
                return_value=(auth_dir, {"source": "auth-dir"}),
            ):
                candidates, source = runtime.find_login_auth_candidates(
                    paths,
                    before_entries,
                    before_metadata=before_metadata,
                )

        self.assertEqual(source["source"], "auth-dir")
        self.assertEqual(candidates, [auth_path])

    def test_refresh_codex_login_session_materializes_changed_existing_auth_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            login_sessions = managed_dir / "login-sessions"
            auth_dir = root / "auth-dir"
            login_sessions.mkdir(parents=True, exist_ok=True)
            auth_dir.mkdir(parents=True, exist_ok=True)
            auth_path = auth_dir / "codex-kir.test.gpt26@gmail.com-team.json"
            auth_path.write_text('{"email":"kir.test.gpt26@gmail.com","version":1}\n', encoding="utf-8")
            paths = runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=auth_dir / "config.yaml",
                auth_file=profile_dir / "auth.json",
                config_toml=profile_dir / "config.toml",
                runtime_mode_file=profile_dir / "runtime-mode.txt",
                runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
                registry_file=managed_dir / "backend-registry.json",
                state_file=managed_dir / "supervisor-state.json",
                managed_config_file=managed_dir / "managed-config.yaml",
                launcher_script=profile_dir / "codex-custom-launch.sh",
                sync_script=managed_dir / "supervisor-sync.sh",
                accounts_bin=managed_dir / "bin" / "codex-accounts",
                onboard_bin=managed_dir / "bin" / "codex-account-onboard",
                lock_file=managed_dir / "wild-boar-proxy.lock",
                launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
                repair_target_inventory_dir=managed_dir / "stable-repair-target",
                repair_target_reference_file=managed_dir / "approved-repair-target.json",
                target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
                stable_runtime_generated_config_file=managed_dir / "stable-runtime-config.generated.yaml",
            )
            session_path = runtime.sandbox_login_session_path(paths, "codex-test-session")
            stdout_path = runtime.codex_login_session_stdout_path(paths, "codex-test-session")
            stderr_path = runtime.codex_login_session_stderr_path(paths, "codex-test-session")
            stdout_path.write_text(
                "Codex device URL: https://auth.openai.com/codex/device\n"
                "Codex device code: TEST-12345\n",
                encoding="utf-8",
            )
            stderr_path.write_text("", encoding="utf-8")
            session = {
                "schema_version": 1,
                "login_session_id": "codex-test-session",
                "provider": "codex",
                "mode": "device",
                "pid": 0,
                "created_at": "2026-05-29T02:44:09+00:00",
                "expires_at": "2026-06-29T02:49:09+00:00",
                "state": "waiting_for_user",
                "device_url": "https://auth.openai.com/codex/device",
                "device_code": "TEST-12345",
                "device_code_present": True,
                "auth_materialized": False,
                "auth_ref": "",
                "auth_inventory_before": [str(auth_path.expanduser().resolve(strict=False))],
                "auth_inventory_before_metadata": {
                    str(auth_path.expanduser().resolve(strict=False)): runtime.login_auth_inventory_entry_metadata(
                        auth_path
                    )
                },
                "auth_inventory_before_digest": "fixture",
                "auth_inventory_source": {"source": "auth-dir"},
                "sandbox_scope": True,
                "inventory_scope": "admitted_owner_login",
                "used": False,
            }
            session_path.write_text(json.dumps(session), encoding="utf-8")
            auth_path.write_text('{"email":"kir.test.gpt26@gmail.com","version":2}\n', encoding="utf-8")

            with unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_auth_inventory_dir",
                return_value=(auth_dir, {"source": "auth-dir"}),
            ):
                refreshed, changed = runtime.refresh_codex_login_session(
                    paths, "codex-test-session"
                )

        self.assertTrue(refreshed["auth_materialized"])
        self.assertEqual(refreshed["state"], "auth_materialized")
        self.assertTrue(
            str(refreshed["auth_ref"]).endswith(
                "codex-kir.test.gpt26@gmail.com-team.json"
            )
        )
        self.assertTrue(any(item.endswith("codex-test-session.json") for item in changed))

    def test_classify_onboarded_backend_selection_accepts_existing_matching_backend_for_explicit_auth_ref(
        self,
    ) -> None:
        auth_ref = "/tmp/codex-existing-auth.json"
        backend = {
            "id": "backend-existing",
            "auth_ref": auth_ref,
            "pool": "reserve",
            "status": "healthy",
            "enabled": True,
        }

        added_ids, selected_backend, selection_status = (
            runtime.classify_onboarded_backend_selection(
                before_registry={"backends": [backend]},
                after_registry={
                    "backends": [dict(backend, updated_at="2026-05-29T00:00:00Z")]
                },
                explicit_auth_ref=auth_ref,
            )
        )

        self.assertEqual(added_ids, [])
        self.assertEqual(selection_status, "selected_existing_backend")
        self.assertIsNotNone(selected_backend)
        self.assertEqual(selected_backend["id"], "backend-existing")


if __name__ == "__main__":
    unittest.main()
