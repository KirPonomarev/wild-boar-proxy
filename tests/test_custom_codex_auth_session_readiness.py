# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import custom_codex_auth_session_readiness as readiness
from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy.core import packets
from wild_boar_proxy.runtime import RuntimePaths


ROOT = Path(__file__).resolve().parents[1]
SECRET = "sk-" + "test-WBPSecretValueForReadinessRedaction123456"


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=managed / "stable-runtime-launcher.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed / "stable-runtime-config.generated.yaml",
    )


def _write_auth(paths: RuntimePaths, payload: dict[str, object]) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    paths.auth_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _process_inventory(paths: RuntimePaths) -> dict[str, object]:
    custom_user_data_dir = str(paths.profile_dir / "electron-user-data")
    app_line = (
        "/Users/example/Applications/Codex WBP Clean.app/Contents/MacOS/Codex "
        f"--user-data-dir={custom_user_data_dir}"
    )
    return {
        "sample": [
            f"101 {app_line}",
            "102 /Users/example/Applications/Codex WBP Clean.app/Contents/Resources/codex app-server --listen unix://sock",
        ],
        "custom_process_lines": [f"101 {app_line}"],
        "default_process_lines": [],
    }


def _process_inventory_with_wrong_user_data() -> dict[str, object]:
    app_line = (
        "/Users/example/Applications/Codex WBP Clean.app/Contents/MacOS/Codex "
        "--user-data-dir=/tmp/not-the-wbp-profile"
    )
    return {
        "sample": [
            f"101 {app_line}",
            "102 /Users/example/Applications/Codex WBP Clean.app/Contents/Resources/codex app-server --listen unix://sock",
        ],
        "custom_process_lines": [],
        "default_process_lines": [],
    }


def _hook_ready_packet() -> dict[str, object]:
    return {
        "packet_kind": "wbp_user_prompt_submit_hook_readiness",
        "status": "ok",
        "machine_error_code": "OK",
        "hook_trusted": True,
        "blocking_reasons": [],
    }


def _hook_blocked_packet() -> dict[str, object]:
    return {
        "packet_kind": "wbp_user_prompt_submit_hook_readiness",
        "status": "error",
        "machine_error_code": "WBP_USER_PROMPT_SUBMIT_HOOK_BLOCKED_TRUST_REQUIRED",
        "hook_trusted": False,
        "blocking_reasons": ["hook_trust_review_required"],
    }


def _account_read(*, account_type: str, requires_openai_auth: bool = False) -> dict[str, object]:
    return {
        "app_server_account_probe_attempted": True,
        "app_server_account_probe_transport_ok": True,
        "app_server_account_probe_electron_user_data_bound": True,
        "app_server_account_probe_electron_user_data_path_recorded": False,
        "app_server_account_response_seen": True,
        "app_server_account_response_has_error": False,
        "app_server_account_response_has_result": True,
        "app_server_account_type": account_type,
        "app_server_account_chatgpt": account_type == "chatgpt",
        "app_server_account_api_key": account_type == "apiKey",
        "app_server_requires_openai_auth": requires_openai_auth,
        "app_server_account_raw_payload_recorded": False,
        "app_server_account_token_recorded": False,
    }


class CustomCodexAuthSessionReadinessTests(unittest.TestCase):
    def test_chatgpt_account_with_live_process_and_trusted_hook_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(account_type="chatgpt"),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["session_state"], readiness.SESSION_STATE_READY)
            self.assertTrue(packet["logged_in_ui_session_proven"])
            self.assertTrue(packet["app_server_account_bound_to_expected_user_data"])
            self.assertTrue(packet["hook_readiness_trusted"])
            self.assertTrue(packet["wbp_clean_app_process_observed"])
            self.assertTrue(packet["wbp_clean_app_server_process_observed"])
            self.assertTrue(packet["custom_user_data_dir_binding_required"])
            self.assertTrue(packet["expected_custom_user_data_dir_observed"])
            self.assertFalse(packet["api_lane_called"])
            self.assertFalse(packet["dispatch_attempted"])
            self.assertFalse(packet["product_ready"])
            self.assertFalse(packet["raw_account_payload_recorded"])
            self.assertFalse(packet["auth_json_content_recorded"])
            self.assertNotIn(SECRET, json.dumps(packet, ensure_ascii=True))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_chatgpt_account_without_electron_user_data_binding_cannot_green_ui_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            account = {
                **_account_read(account_type="chatgpt"),
                "app_server_account_probe_electron_user_data_bound": False,
            }

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=account,
            )

            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["logged_in_ui_session_proven"])
            self.assertFalse(packet["app_server_account_bound_to_expected_user_data"])
            self.assertIn(
                "app_server_account_electron_user_data_not_bound",
                packet["blocking_reasons"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_chatgpt_account_with_openai_auth_requirement_still_proves_login(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(
                    account_type="chatgpt",
                    requires_openai_auth=True,
                ),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["session_state"], readiness.SESSION_STATE_READY)
            self.assertTrue(packet["logged_in_ui_session_proven"])
            self.assertTrue(packet["app_server_requires_openai_auth"])
            self.assertNotIn("custom_codex_login_required", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_account_probe_home_copies_auth_without_runtime_provider_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            paths.config_toml.write_text(
                "\n".join(
                    [
                        'model_provider = "wbp"',
                        "",
                        "[model_providers.wbp]",
                        'base_url = "http://127.0.0.1:8318/v1"',
                        "requires_openai_auth = false",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            probe_root = Path(temp_dir) / "probe"

            probe_home, metadata = readiness._prepare_account_probe_codex_home(
                paths,
                probe_root,
            )

            self.assertTrue((probe_home / "auth.json").exists())
            self.assertFalse((probe_home / "config.toml").exists())
            self.assertTrue(metadata["app_server_account_probe_auth_shadow_home"])
            self.assertTrue(metadata["app_server_account_probe_runtime_config_isolated"])
            self.assertTrue(metadata["app_server_account_probe_auth_json_copied"])
            self.assertFalse(metadata["app_server_account_probe_config_toml_copied"])
            self.assertFalse(metadata["app_server_account_probe_auth_json_source_recorded"])
            self.assertEqual(
                json.loads((probe_home / "auth.json").read_text(encoding="utf-8")),
                {"auth_mode": "chatgpt", "access_token": SECRET},
            )

    def test_api_key_only_blocks_and_never_counts_as_ui_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"OPENAI_API_KEY": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(account_type="apiKey"),
            )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_API_KEY_ONLY,
            )
            self.assertTrue(packet["api_key_only"])
            self.assertFalse(packet["api_key_only_counts_as_ui_session"])
            self.assertFalse(packet["logged_in_ui_session_proven"])
            self.assertIn("api_key_only_not_ui_session", packet["blocking_reasons"])
            self.assertNotIn(SECRET, json.dumps(packet, ensure_ascii=True))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_login_required_blocks_without_api_key_or_chatgpt_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(
                    account_type="",
                    requires_openai_auth=True,
                ),
            )

            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_LOGIN_REQUIRED,
            )
            self.assertTrue(packet["custom_codex_login_required"])
            self.assertIn("custom_codex_login_required", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_process_inventory_must_be_live_and_wbp_clean_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory={"sample": []},
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(account_type="chatgpt"),
            )

            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_PROCESS_NOT_LIVE,
            )
            self.assertFalse(packet["process_inventory_raw_lines_recorded"])
            self.assertIn("wbp_clean_app_process_not_observed", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_process_inventory_must_match_expected_custom_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory_with_wrong_user_data(),
                process_inventory_live=True,
                hook_readiness_packet=_hook_ready_packet(),
                account_read_metadata=_account_read(account_type="chatgpt"),
            )

            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_PROCESS_NOT_LIVE,
            )
            self.assertTrue(packet["wbp_clean_app_process_observed"])
            self.assertTrue(packet["wbp_clean_app_server_process_observed"])
            self.assertFalse(packet["expected_custom_user_data_dir_observed"])
            self.assertFalse(packet["process_inventory_raw_lines_recorded"])
            self.assertIn("custom_user_data_dir_not_observed", packet["blocking_reasons"])
            self.assertNotIn(str(paths.profile_dir), json.dumps(packet, ensure_ascii=True))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_hook_readiness_must_be_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=_hook_blocked_packet(),
                account_read_metadata=_account_read(account_type="chatgpt"),
            )

            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_HOOK_NOT_READY,
            )
            self.assertFalse(packet["hook_readiness_trusted"])
            self.assertIn("user_prompt_submit_hook_not_ready", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_hook_readiness_must_match_app_server_trust_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            hook_packet = {
                **_hook_ready_packet(),
                "codex_hook_current_hash_source": "codex_app_server_hooks_list",
                "codex_hook_trust_status_from_app_server": "untrusted",
                "codex_hook_app_server_trust_status_required": True,
                "codex_hook_app_server_trust_status_trusted": False,
                "blocking_reasons": [
                    "codex_hook_app_server_trust_status_not_trusted",
                ],
            }

            packet = readiness.build_custom_codex_auth_session_readiness_packet(
                paths=paths,
                process_inventory=_process_inventory(paths),
                process_inventory_live=True,
                hook_readiness_packet=hook_packet,
                account_read_metadata=_account_read(account_type="chatgpt"),
            )

            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_HOOK_NOT_READY,
            )
            self.assertFalse(packet["hook_readiness_trusted"])
            self.assertIn("user_prompt_submit_hook_not_ready", packet["blocking_reasons"])
            self.assertIn(
                "codex_hook_app_server_trust_status_not_trusted",
                packet["blocking_reasons"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_account_probe_is_bound_to_expected_electron_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            expected_user_data_dir = str(paths.profile_dir / "electron-user-data")

            with mock.patch.object(
                readiness,
                "probe_codex_app_server_account_read",
                return_value={
                    **_account_read(account_type="chatgpt"),
                    "app_server_account_probe_electron_user_data_bound": True,
                    "app_server_account_probe_electron_user_data_path_recorded": False,
                },
            ) as probe:
                packet = readiness.build_custom_codex_auth_session_readiness_packet(
                    paths=paths,
                    process_inventory=_process_inventory(paths),
                    process_inventory_live=True,
                    hook_readiness_packet=_hook_ready_packet(),
                )

            self.assertEqual(packet["status"], "ok")
            probe.assert_called_once()
            _, kwargs = probe.call_args
            self.assertEqual(kwargs["electron_user_data_dir"], expected_user_data_dir)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_account_probe_exports_electron_user_data_env_without_recording_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            fake_binary = root / "codex"
            fake_binary.write_text("#!/bin/sh\n", encoding="utf-8")
            fake_binary.chmod(0o755)
            expected_user_data_dir = str(paths.profile_dir / "electron-user-data")
            captured_env: dict[str, str] = {}

            class FakeProcess:
                def poll(self) -> None:
                    return None

                def terminate(self) -> None:
                    return None

                def wait(self, timeout: float | None = None) -> int:
                    return 0

            def fake_popen(argv: list[str], **kwargs: object) -> FakeProcess:
                captured_env.update(dict(kwargs["env"]))  # type: ignore[index]
                socket_arg = str(argv[-1]).removeprefix("unix://")
                Path(socket_arg).touch()
                return FakeProcess()

            with (
                mock.patch.object(readiness, "_codex_app_server_binary", return_value=fake_binary),
                mock.patch.object(subprocess, "Popen", side_effect=fake_popen),
            ):
                packet = readiness.probe_codex_app_server_account_read(
                    paths,
                    electron_user_data_dir=expected_user_data_dir,
                    timeout_seconds=0.01,
                )

            self.assertEqual(
                captured_env["CODEX_ELECTRON_USER_DATA_PATH"],
                expected_user_data_dir,
            )
            self.assertTrue(captured_env["CODEX_HOME"].endswith("/codex-home"))
            self.assertNotEqual(captured_env["CODEX_HOME"], str(paths.profile_dir))
            self.assertTrue(packet["app_server_account_probe_electron_user_data_bound"])
            self.assertFalse(
                packet["app_server_account_probe_electron_user_data_path_recorded"]
            )

    def test_cli_emits_strict_json_without_green_from_provided_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_auth(paths, {"auth_mode": "chatgpt", "access_token": SECRET})
            inventory_file = root / "inventory.json"
            inventory_file.write_text(
                json.dumps(_process_inventory(paths)) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
            env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
            env["WBP_CONFIG_TOML"] = str(paths.config_toml)
            env["WBP_AUTH_FILE"] = str(paths.auth_file)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "custom-codex-auth-session-readiness",
                    "--process-inventory-file",
                    str(inventory_file),
                    "--skip-hook-readiness-probe",
                    "--skip-account-app-server-probe",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            packet = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
            self.assertEqual(packet["effect"], "probe")
            self.assertEqual(
                packet["machine_error_code"],
                readiness.CUSTOM_CODEX_AUTH_SESSION_PROCESS_NOT_LIVE,
            )
            self.assertFalse(packet["process_inventory_live"])
            self.assertFalse(packet["product_ready"])
            self.assertNotIn(SECRET, result.stdout)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_dispatch_forwards_default_probe_arguments(self) -> None:
        packet = packets.build_command_packet(
            ok=False,
            human_message="blocked",
            machine_error_code=readiness.CUSTOM_CODEX_AUTH_SESSION_LOGIN_REQUIRED,
            liveness="degraded",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            effect="probe",
            extra={
                "packet_kind": readiness.CUSTOM_CODEX_AUTH_SESSION_READINESS_PACKET_KIND,
                "product_ready": False,
                "api_lane_called": False,
                "dispatch_attempted": False,
            },
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_custom_codex_auth_session_readiness_command",
                return_value=packet,
            ) as command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "custom-codex-auth-session-readiness",
                    "--custom-user-data-dir",
                    "/tmp/wbp-custom-user-data",
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 1)
        emitted = json.loads(stdout.getvalue())
        self.assertEqual(emitted["packet_kind"], packet["packet_kind"])
        command.assert_called_once()
        _, kwargs = command.call_args
        self.assertEqual(kwargs["custom_user_data_dir"], "/tmp/wbp-custom-user-data")
        self.assertIsNone(kwargs["process_inventory_file"])
        self.assertTrue(kwargs["probe_hook_readiness"])
        self.assertTrue(kwargs["probe_account_app_server"])
        self.assertEqual(packets.inspect_command_packet_semantics(emitted), [])


if __name__ == "__main__":
    unittest.main()
