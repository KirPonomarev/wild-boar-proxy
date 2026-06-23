# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import io
import os
from pathlib import Path
import tempfile
import unittest
import unittest.mock

from wild_boar_proxy import runtime
from wild_boar_proxy.process_runner import DetachedProcessStartResult


def _runtime_paths(root: Path) -> runtime.RuntimePaths:
    profile_dir = root / "profile"
    managed_dir = profile_dir / "managed"
    stable_dir = root / "stable"
    return runtime.RuntimePaths(
        profile_dir=profile_dir,
        managed_dir=managed_dir,
        stable_config=stable_dir / "config.yaml",
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
        stable_runtime_generated_config_file=managed_dir
        / "stable-runtime-config.generated.yaml",
    )


class RuntimeNativeAuthRecoveryTests(unittest.TestCase):
    def test_repo_owned_default_launcher_enables_renderer_accessibility_for_desktop_app(
        self,
    ) -> None:
        payload = runtime.build_repo_owned_default_launcher_script_payload()

        self.assertIn(
            'CODEX_RENDERER_ACCESSIBILITY_FLAG="--force-renderer-accessibility=complete"',
            payload,
        )
        self.assertEqual(
            payload.count(' "$CODEX_RENDERER_ACCESSIBILITY_FLAG"'),
            1,
        )
        self.assertIn(
            'CODEX_REMOTE_DEBUGGING_ADDRESS="127.0.0.1"',
            payload,
        )
        self.assertIn(
            'CODEX_REMOTE_DEBUGGING_PORT="${WBP_CODEX_REMOTE_DEBUGGING_PORT:-9223}"',
            payload,
        )
        self.assertEqual(
            payload.count('"--remote-debugging-address=$CODEX_REMOTE_DEBUGGING_ADDRESS"'),
            1,
        )
        self.assertEqual(
            payload.count('"--remote-debugging-port=$CODEX_REMOTE_DEBUGGING_PORT"'),
            1,
        )
        self.assertIn(
            '"--remote-debugging-port=$CODEX_REMOTE_DEBUGGING_PORT" "--user-data-dir=$APP_USER_DATA_DIR"',
            payload,
        )

    def test_repo_owned_default_launcher_detaches_desktop_app_from_shell(
        self,
    ) -> None:
        payload = runtime.build_repo_owned_default_launcher_script_payload()

        self.assertIn(
            'SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"',
            payload,
        )
        self.assertIn('PROFILE_DIR="${WBP_PROFILE_DIR:-$SCRIPT_DIR}"', payload)
        self.assertNotIn(
            'PROFILE_DIR="${WBP_PROFILE_DIR:-$HOME/.codex-custom-cli}"',
            payload,
        )
        self.assertIn("launch_codex_app() {", payload)
        self.assertNotIn('nohup "$CODEX_APP_BIN"', payload)
        self.assertNotIn("nohup env HTTP_PROXY=", payload)
        self.assertIn('/usr/bin/open -n "$CODEX_APP_PATH" --args', payload)
        self.assertIn("set_launch_env", payload)
        self.assertIn("find_launched_pid() {", payload)
        self.assertIn('printf "%s\\n" "$launched_pid" > "$APP_PID_FILE"', payload)
        self.assertIn('launch_codex_app "--open-project=$WORKSPACE_PATH"', payload)
        self.assertIn("  launch_codex_app\n  sleep 3", payload)

    def test_repo_owned_default_launcher_preserves_owner_external_models_root(
        self,
    ) -> None:
        payload = runtime.build_repo_owned_default_launcher_script_payload()

        owner_root_line = (
            'OWNER_EXTERNAL_MODELS_DIR="${WBP_OWNER_EXTERNAL_MODELS_DIR:-'
            '${WBP_EXTERNAL_MODELS_DIR:-$HOME/.wild-boar-proxy/external-models}}"'
        )
        export_line = 'export WBP_EXTERNAL_MODELS_DIR="$OWNER_EXTERNAL_MODELS_DIR"'
        home_line = 'export HOME="$APP_HOME"'
        self.assertIn(owner_root_line, payload)
        self.assertIn(export_line, payload)
        self.assertLess(payload.index(owner_root_line), payload.index(home_line))
        self.assertLess(payload.index(export_line), payload.index(home_line))
        self.assertNotIn("DEEPSEEK_API_KEY", payload)
        self.assertNotIn("OPENROUTER_API_KEY", payload)

    def test_repo_owned_default_launcher_unsets_global_api_key_for_chatgpt_auth(
        self,
    ) -> None:
        payload = runtime.build_repo_owned_default_launcher_script_payload()

        self.assertIn('AUTH_MODE="$(${WBP_PYTHON_BIN:-/usr/bin/python3}', payload)
        self.assertIn("print(str(data.get(\"auth_mode\", \"\")).strip().lower())", payload)
        self.assertIn('OPENAI_API_KEY_FROM_AUTH="$(${WBP_PYTHON_BIN:-/usr/bin/python3}', payload)
        self.assertIn('if [ "$AUTH_MODE" = "chatgpt" ]; then', payload)
        self.assertIn('unset OPENAI_API_KEY', payload)
        self.assertIn('elif [ -n "$OPENAI_API_KEY_FROM_AUTH" ]; then', payload)
        self.assertIn('export OPENAI_API_KEY="$OPENAI_API_KEY_FROM_AUTH"', payload)

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

    def test_native_auth_recovery_hint_recommends_repair_for_unloaded_selected_backend(
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

        self.assertEqual(hint["status"], "runtime_auth_gap_repair_recommended")
        self.assertFalse(hint["owner_action_required"])
        self.assertEqual(hint["next_action"], "run_healthcheck_repair_if_authorized")
        self.assertEqual(
            hint["command_surface"],
            "healthcheck --repair --json",
        )
        self.assertEqual(
            hint["reason"],
            "auth_unavailable_with_selected_backend_not_loaded",
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

    def test_refresh_codex_login_session_does_not_revive_expired_materialized_session(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = _runtime_paths(root)
            auth_dir = root / "stable"
            (paths.managed_dir / "login-sessions").mkdir(parents=True, exist_ok=True)
            auth_dir.mkdir(parents=True, exist_ok=True)
            auth_path = auth_dir / "codex-expired.json"
            auth_path.write_text('{"email":"expired@example.com"}\n', encoding="utf-8")
            session_path = runtime.sandbox_login_session_path(
                paths, "codex-expired-session"
            )
            session_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "login_session_id": "codex-expired-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 0,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2000-01-01T00:00:00+00:00",
                        "state": "expired",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "OLD-CODE",
                        "device_code_present": True,
                        "auth_materialized": True,
                        "auth_ref": str(auth_path),
                        "auth_inventory_before": [str(auth_path)],
                        "auth_inventory_before_metadata": {},
                        "auth_inventory_before_digest": "fixture",
                        "auth_inventory_source": {"source": "auth-dir"},
                        "sandbox_scope": True,
                        "inventory_scope": "admitted_owner_login",
                        "used": False,
                    }
                ),
                encoding="utf-8",
            )

            with unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_auth_inventory_dir",
                return_value=(auth_dir, {"source": "auth-dir"}),
            ):
                refreshed, changed = runtime.refresh_codex_login_session(
                    paths, "codex-expired-session"
                )

        self.assertEqual(refreshed["state"], "expired")
        self.assertTrue(refreshed["auth_materialized"])
        self.assertEqual(changed, [])

    def test_run_accounts_login_start_skips_expired_reused_codex_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = _runtime_paths(root)
            stable_dir = root / "stable"
            (paths.managed_dir / "login-sessions").mkdir(parents=True, exist_ok=True)
            (paths.managed_dir / "bin").mkdir(parents=True, exist_ok=True)
            stable_dir.mkdir(parents=True, exist_ok=True)
            paths.stable_config.write_text(
                f'host: 127.0.0.1\nport: 8318\nauth-dir: "{stable_dir}"\n',
                encoding="utf-8",
            )
            fake_cli = paths.managed_dir / "bin" / "fake-cli-proxy"
            fake_cli.write_text("", encoding="utf-8")
            fake_cli.chmod(0o755)
            old_session_path = runtime.sandbox_login_session_path(
                paths, "codex-expired-session"
            )
            old_session_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "login_session_id": "codex-expired-session",
                        "provider": "codex",
                        "mode": "device",
                        "pid": 0,
                        "created_at": "2026-05-29T02:44:09+00:00",
                        "expires_at": "2000-01-01T00:00:00+00:00",
                        "state": "expired",
                        "device_url": "https://auth.openai.com/codex/device",
                        "device_code": "OLD-CODE",
                        "device_code_present": True,
                        "auth_materialized": True,
                        "auth_ref": str(stable_dir / "codex-expired.json"),
                        "auth_inventory_before": [],
                        "auth_inventory_before_metadata": {},
                        "auth_inventory_before_digest": "fixture",
                        "auth_inventory_source": {"source": "auth-dir"},
                        "sandbox_scope": True,
                        "inventory_scope": "admitted_owner_login",
                        "used": False,
                    }
                ),
                encoding="utf-8",
            )

            def fake_start_detached_process(*args, **kwargs):
                stdout_handle = kwargs["stdout"]
                assert isinstance(stdout_handle, io.TextIOBase)
                stdout_handle.write(
                    "Codex device URL: https://auth.openai.com/codex/device\n"
                    "Codex device code: NEW-CODE\n"
                )
                stdout_handle.flush()
                return DetachedProcessStartResult(
                    status="ok",
                    machine_error_code=runtime.PROCESS_OK,
                    pid=os.getpid() + 1000,
                    launch_observed=True,
                    error="",
                    duration_seconds=0.01,
                )

            with (
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.resolve_cli_proxy_bin",
                    return_value=fake_cli,
                ),
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.start_detached_process",
                    side_effect=fake_start_detached_process,
                ),
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.login_session_pid_is_running",
                    return_value=True,
                ),
            ):
                payload = runtime.run_accounts_login_start(
                    paths, "codex", mode="device"
                )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["device_code"], "NEW-CODE")
        self.assertNotEqual(payload["session_id"], "codex-expired-session")
        self.assertEqual(payload["next_action"], "wait_for_login")

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

    def test_refresh_codex_login_session_marks_failed_when_handoff_process_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            auth_dir = root / "auth-dir"
            login_sessions_dir = managed_dir / "login-sessions"
            login_sessions_dir.mkdir(parents=True, exist_ok=True)
            auth_dir.mkdir(parents=True, exist_ok=True)
            paths = runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=root / "stable" / "config.yaml",
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
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )
            session_path = runtime.sandbox_login_session_path(paths, "codex-test-session")
            stdout_path = runtime.codex_login_session_stdout_path(paths, "codex-test-session")
            stderr_path = runtime.codex_login_session_stderr_path(paths, "codex-test-session")
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
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
                "pid": 999999,
                "created_at": "2026-05-29T02:44:09+00:00",
                "expires_at": "2026-06-29T02:49:09+00:00",
                "state": "waiting_for_user",
                "device_url": "https://auth.openai.com/codex/device",
                "device_code": "TEST-12345",
                "device_code_present": True,
                "auth_materialized": False,
                "auth_ref": "",
                "auth_inventory_before": [],
                "auth_inventory_before_metadata": {},
                "auth_inventory_before_digest": "fixture",
                "auth_inventory_source": {"source": "auth-dir"},
                "sandbox_scope": True,
                "inventory_scope": "admitted_owner_login",
                "used": False,
            }
            session_path.write_text(json.dumps(session), encoding="utf-8")

            with unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_auth_inventory_dir",
                return_value=(auth_dir, {"source": "auth-dir"}),
            ):
                refreshed, changed = runtime.refresh_codex_login_session(
                    paths, "codex-test-session"
                )

        self.assertEqual(refreshed["state"], "failed")
        self.assertEqual(
            refreshed["failure_reason"],
            "device_handoff_process_exited_before_auth_materialized",
        )
        self.assertTrue(any(item.endswith("codex-test-session.json") for item in changed))

    def test_run_accounts_login_start_spawns_detached_codex_device_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            stable_dir = root / "stable"
            auth_dir = stable_dir
            (managed_dir / "login-sessions").mkdir(parents=True, exist_ok=True)
            (managed_dir / "bin").mkdir(parents=True, exist_ok=True)
            stable_dir.mkdir(parents=True, exist_ok=True)
            auth_dir.mkdir(parents=True, exist_ok=True)
            stable_config = stable_dir / "config.yaml"
            stable_config.write_text(
                f'host: 127.0.0.1\nport: 8318\nauth-dir: "{auth_dir}"\n',
                encoding="utf-8",
            )
            fake_cli = managed_dir / "bin" / "fake-cli-proxy"
            fake_cli.write_text("", encoding="utf-8")
            fake_cli.chmod(0o755)
            paths = runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=stable_config,
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
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )

            start_kwargs: dict[str, object] = {}

            def fake_start_detached_process(*args, **kwargs):
                nonlocal start_kwargs
                start_kwargs = kwargs
                stdout_handle = kwargs["stdout"]
                assert isinstance(stdout_handle, io.TextIOBase)
                stdout_handle.write(
                    "Codex device URL: https://auth.openai.com/codex/device\n"
                    "Codex device code: TEST-DETACH\n"
                )
                stdout_handle.flush()
                return DetachedProcessStartResult(
                    status="ok",
                    machine_error_code=runtime.PROCESS_OK,
                    pid=os.getpid() + 1000,
                    launch_observed=True,
                    error="",
                    duration_seconds=0.01,
                )

            with (
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.resolve_cli_proxy_bin",
                    return_value=fake_cli,
                ),
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.start_detached_process",
                    side_effect=fake_start_detached_process,
                ),
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.login_session_pid_is_running",
                    return_value=True,
                ),
            ):
                payload = runtime.run_accounts_login_start(paths, "codex", mode="device")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["device_code"], "TEST-DETACH")
        self.assertEqual(start_kwargs["cwd"], paths.profile_dir)
        self.assertTrue(start_kwargs["text"])

    def test_run_accounts_login_start_reports_detached_launch_failure_without_ready_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_dir = root / "profile"
            managed_dir = profile_dir / "managed"
            stable_dir = root / "stable"
            auth_dir = stable_dir
            (managed_dir / "login-sessions").mkdir(parents=True, exist_ok=True)
            (managed_dir / "bin").mkdir(parents=True, exist_ok=True)
            stable_dir.mkdir(parents=True, exist_ok=True)
            auth_dir.mkdir(parents=True, exist_ok=True)
            stable_config = stable_dir / "config.yaml"
            stable_config.write_text(
                f'host: 127.0.0.1\nport: 8318\nauth-dir: "{auth_dir}"\n',
                encoding="utf-8",
            )
            fake_cli = managed_dir / "bin" / "fake-cli-proxy"
            fake_cli.write_text("", encoding="utf-8")
            fake_cli.chmod(0o755)
            paths = runtime.RuntimePaths(
                profile_dir=profile_dir,
                managed_dir=managed_dir,
                stable_config=stable_config,
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
                stable_runtime_generated_config_file=managed_dir
                / "stable-runtime-config.generated.yaml",
            )

            failed_start = DetachedProcessStartResult(
                status="error",
                machine_error_code=runtime.PROCESS_FAILED,
                pid=None,
                launch_observed=False,
                error="launch failed",
                duration_seconds=0.01,
            )
            with (
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.resolve_cli_proxy_bin",
                    return_value=fake_cli,
                ),
                unittest.mock.patch(
                    "wild_boar_proxy.runtime.start_detached_process",
                    return_value=failed_start,
                ),
            ):
                payload = runtime.run_accounts_login_start(paths, "codex", mode="device")
            session_id = payload["session_id"]
            session_path = managed_dir / "login-sessions" / f"{session_id}.json"
            self.assertTrue(session_path.is_file())
            session = json.loads(session_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "LOGIN_DEVICE_PROCESS_START_FAILED")
        self.assertEqual(payload["next_action"], "retry")
        self.assertEqual(payload["process_result"]["machine_error_code"], runtime.PROCESS_FAILED)
        self.assertFalse(payload["process_result"]["launch_observed"])
        self.assertEqual(payload["login_result"]["status"], "failed")
        self.assertFalse(payload["login_result"]["device_code_present"])
        self.assertEqual(session["state"], "failed")
        self.assertEqual(session["failure_reason"], "device_process_start_failed")

    def test_terminate_login_session_pid_prefers_process_group_with_pid_fallback(
        self,
    ) -> None:
        calls: list[tuple[str, int, int]] = []
        running_checks = [True, False]

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))

        def fake_kill(pid: int, sig: int) -> None:
            calls.append(("kill", pid, sig))

        def fake_is_running(pid: int) -> bool:
            return running_checks.pop(0) if running_checks else False

        with (
            unittest.mock.patch("wild_boar_proxy.runtime.os.killpg", side_effect=fake_killpg),
            unittest.mock.patch("wild_boar_proxy.runtime.os.kill", side_effect=fake_kill),
            unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_pid_is_running",
                side_effect=fake_is_running,
            ),
            unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_cancel_grace_seconds",
                return_value=0.2,
            ),
        ):
            terminated = runtime.terminate_login_session_pid(12345)

        self.assertTrue(terminated)
        self.assertEqual(calls, [("killpg", 12345, runtime.signal.SIGTERM)])

    def test_terminate_login_session_pid_falls_back_when_process_group_missing(
        self,
    ) -> None:
        calls: list[tuple[str, int, int]] = []
        running_checks = [True, False]

        def fake_killpg(pid: int, sig: int) -> None:
            calls.append(("killpg", pid, sig))
            raise ProcessLookupError

        def fake_kill(pid: int, sig: int) -> None:
            calls.append(("kill", pid, sig))

        def fake_is_running(pid: int) -> bool:
            return running_checks.pop(0) if running_checks else False

        with (
            unittest.mock.patch("wild_boar_proxy.runtime.os.killpg", side_effect=fake_killpg),
            unittest.mock.patch("wild_boar_proxy.runtime.os.kill", side_effect=fake_kill),
            unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_pid_is_running",
                side_effect=fake_is_running,
            ),
            unittest.mock.patch(
                "wild_boar_proxy.runtime.login_session_cancel_grace_seconds",
                return_value=0.2,
            ),
        ):
            terminated = runtime.terminate_login_session_pid(12345)

        self.assertTrue(terminated)
        self.assertEqual(
            calls,
            [
                ("killpg", 12345, runtime.signal.SIGTERM),
                ("kill", 12345, runtime.signal.SIGTERM),
            ],
        )


if __name__ == "__main__":
    unittest.main()
