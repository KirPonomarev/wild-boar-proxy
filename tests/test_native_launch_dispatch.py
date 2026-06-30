# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import wild_boar_proxy.native_window_probe as native_probe
import wild_boar_proxy.native_filesystem_probe as native_fs
from wild_boar_proxy.custom_codex_native_ui_observer_proof import (
    NATIVE_UI_AUTO_LAUNCH_PACKET_FILE_NAME,
    run_native_ui_observer_proof_command,
)
from wild_boar_proxy.native_launch_contract import build_native_custom_preflight_packet
from wild_boar_proxy.native_launch_dispatch import (
    build_native_cleanup_rollback_execution_packet,
    build_native_current_codex_protection_packet,
    build_native_custom_dispatch_blocked_packet,
    build_native_custom_dispatch_packet,
    build_native_dispatch_authorization_packet,
    build_native_dispatch_false_green_audit,
    build_native_original_dispatch_deferred_packet,
    build_native_process_observation_packet,
    build_native_window_observation_packet,
    build_native_window_usability_packet,
)
from wild_boar_proxy.native_window_probe import (
    OWNER_STANDING_AUTHORIZATION_PHRASE,
    launch_custom_native_app_packet,
    native_window_probe_command,
    native_window_probe_server_plan,
    owner_authorization_phrase_present,
)

ROOT = Path(__file__).resolve().parents[1]


def native_command() -> dict[str, object]:
    return {
        "schema_version": 1,
        "command_id": "cmd-native",
        "launch_mode": "CODEX_CUSTOM_NATIVE_APP",
    }


def custom_admission_plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "target_candidate_source": "repo_or_server_owned_launcher_candidate",
        "isolated_home_plan": True,
        "isolated_codex_home_plan": True,
        "isolated_profile_data_dir_plan": True,
        "isolated_app_support_dir_plan": True,
        "isolated_cache_dir_plan": True,
        "isolated_runtime_dir_plan": True,
        "keychain_reset_prompt_blocker_plan": True,
        "server_planned_route_endpoint": True,
        "port_separation_plan": True,
        "cleanup_command_plan": True,
        "rollback_expectation_declared": True,
        "current_codex_snapshot_plan": True,
        "write_surfaces_declared": True,
        "declared_write_surfaces": [
            "server_owned_temp_home",
            "server_owned_temp_codex_home",
            "server_owned_profile_dir",
            "server_owned_app_support_dir",
            "server_owned_cache_dir",
            "server_owned_runtime_dir",
            "launch_receipt",
        ],
    }
    plan.update(overrides)
    return plan


def admitted_custom_packet(**overrides: object) -> dict[str, object]:
    return build_native_custom_preflight_packet(
        native_command(),
        custom_admission_plan(**overrides),
    )


def advertised_model_packet(model: str = "gpt-5.5") -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "configured_model_id": model,
        "configured_model_available": True,
        "available_model_ids": [model],
        "models_endpoint_probe_attempted": True,
        "models_endpoint_redacted": True,
    }


class NativeLaunchDispatchTests(unittest.TestCase):
    def test_native_response_request_binding_texts_include_safe_slug_variant(self) -> None:
        self.assertEqual(
            native_probe._native_free_text_request_binding_texts(
                "physical-natural-1782797606"
            ),
            ["physical-natural-1782797606", "physical_natural_1782797606"],
        )
        self.assertEqual(
            native_probe._native_free_text_request_binding_texts("plain123"),
            ["plain123"],
        )

    def test_native_window_probe_runner_command_matches_custom_native_mode(self) -> None:
        command = native_window_probe_command()
        self.assertEqual(command["schema_version"], 1)
        self.assertEqual(command["command_id"], "cmd-native-window-proof")
        self.assertEqual(command["launch_mode"], "CODEX_CUSTOM_NATIVE_APP")

    def test_native_window_probe_server_plan_keeps_repo_canonical_isolated_home_lane(self) -> None:
        plan = native_window_probe_server_plan()
        self.assertTrue(plan["isolated_home_plan"])
        self.assertTrue(plan["isolated_codex_home_plan"])
        self.assertTrue(plan["isolated_profile_data_dir_plan"])
        self.assertTrue(plan["isolated_app_support_dir_plan"])
        self.assertTrue(plan["isolated_cache_dir_plan"])
        self.assertTrue(plan["isolated_runtime_dir_plan"])
        self.assertTrue(plan["keychain_reset_prompt_blocker_plan"])
        self.assertTrue(plan["server_planned_route_endpoint"])

    def test_owner_authorization_phrase_present_requires_exact_phrase(self) -> None:
        self.assertTrue(owner_authorization_phrase_present(OWNER_STANDING_AUTHORIZATION_PHRASE))
        self.assertTrue(owner_authorization_phrase_present(f" {OWNER_STANDING_AUTHORIZATION_PHRASE} "))
        self.assertFalse(owner_authorization_phrase_present("go"))

    def test_launch_native_candidate_allocates_profile_remote_debugging_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_dir = temp_root / "profile"
            layout = native_fs.NativeProbeLayout(
                tmp_root=temp_root,
                profile_dir=profile_dir,
                launcher_path=profile_dir / "codex-custom-launch.sh",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                custom_user_data_dir=profile_dir / "electron-user-data",
                custom_home_dir=profile_dir / "home",
                custom_codex_home=profile_dir,
                custom_tmp_dir=profile_dir / "tmp",
            )
            process = SimpleNamespace(pid=777, poll=mock.Mock(return_value=None))
            inventory = {
                "custom_process_count": 1,
                "custom_process_lines": [
                    f"222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir={layout.custom_user_data_dir}"
                ],
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe._allocate_loopback_remote_debugging_port",
                    return_value=49231,
                ),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.collect_codex_process_inventory",
                    return_value=inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.subprocess.Popen",
                    return_value=process,
                ) as popen,
                mock.patch("wild_boar_proxy.native_filesystem_probe.time.sleep"),
            ):
                packet = native_fs.launch_native_candidate(
                    repo_root=ROOT,
                    layout=layout,
                    real_runtime_paths=SimpleNamespace(
                        managed_dir=temp_root / "managed",
                        stable_config=temp_root / "config.yaml",
                    ),
                )
                recorded_port_text = native_fs.remote_debugging_port_file(
                    profile_dir
                ).read_text(encoding="utf-8").strip()
                env_port = popen.call_args.kwargs["env"][
                    "WBP_CODEX_REMOTE_DEBUGGING_PORT"
                ]

        self.assertEqual(packet["remote_debugging_port"], 49231)
        self.assertEqual(
            packet["remote_debugging_port_source"],
            "allocated_loopback_launch_port",
        )
        self.assertTrue(packet["remote_debugging_port_file_written"])
        self.assertFalse(packet["remote_debugging_port_file_path_recorded"])
        self.assertEqual(recorded_port_text, "49231")
        self.assertEqual(env_port, "49231")

    def test_live_custom_native_launch_returns_structured_blocked_packet_on_exception(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
            side_effect=RuntimeError("boom"),
        ):
            packet = launch_custom_native_app_packet(
                repo_root=ROOT,
                endpoint="http://127.0.0.1:8318/v1",
                model="gpt-5.3-codex",
                owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_LAUNCH_EXCEPTION")
        self.assertEqual(packet["next_action"], "stop_and_diagnose_native_launch_exception")
        self.assertEqual(packet["cleanup_result"]["exception_class"], "RuntimeError")
        self.assertFalse(packet["keychain_preflight_attempted"])
        self.assertEqual(packet["keychain_preflight_status"], "")
        self.assertFalse(packet["isolated_default_keychain_verified"])
        self.assertFalse(packet["isolated_search_list_verified"])
        self.assertEqual(packet["prompt_avoidance_claim_scope"], "keychain_not_found_prompt_only")

    def test_live_custom_native_launch_blocks_before_keychain_when_model_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            blocked_materialize = {
                "status": "blocked",
                "machine_error_code": (
                    "CUSTOM_NATIVE_CONFIG_MODEL_NOT_IN_MODELS_ENDPOINT"
                ),
                "human_message": "model unavailable",
                "next_action": "select_model_advertised_by_local_models_endpoint",
                "configured_model_validation_attempted": True,
                "configured_model_available": False,
                "configured_model_validation_packet": {
                    "status": "blocked",
                    "machine_error_code": (
                        "CUSTOM_NATIVE_CONFIG_MODEL_NOT_IN_MODELS_ENDPOINT"
                    ),
                    "configured_model_id": "gpt-5.3-codex",
                },
                "model_config_written": False,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=root / "managed"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.emit_local_token",
                    return_value="local-token",
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.materialize_probe_profile",
                    return_value=blocked_materialize,
                ) as materialize,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain"
                ) as keychain,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=root,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_CONFIG_MODEL_NOT_IN_MODELS_ENDPOINT",
        )
        self.assertTrue(packet["configured_model_validation_attempted"])
        self.assertFalse(packet["configured_model_available"])
        self.assertFalse(packet["model_config_written"])
        self.assertEqual(packet["selection_model_id"], "gpt-5.3-codex")
        self.assertEqual(
            packet["next_action"],
            "select_model_advertised_by_local_models_endpoint",
        )
        self.assertTrue(packet["cleanup_result"]["attempted"])
        self.assertTrue(materialize.call_args.kwargs["validate_model_against_endpoint"])
        keychain.assert_not_called()

    def test_window_observation_uses_custom_pid_and_requires_real_window_count(self) -> None:
        process_inventory = {
            "root_app_pids": [111, 222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
            ],
        }
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex\ttrue\tfalse\tfalse\t0\n",
            stderr="",
        )
        with mock.patch("wild_boar_proxy.native_window_probe.subprocess.run", return_value=completed) as run:
            packet = native_probe._window_observation_via_ax(process_inventory)

        self.assertFalse(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 222)
        self.assertEqual(packet["window_count"], 0)
        self.assertEqual(packet["blocked_reason_class"], "pid_visible_but_accessible_window_absent")
        self.assertIn("unix id is 222", run.call_args.args[0][2])

    def test_window_observation_accepts_pid_bound_cg_window_when_ax_count_is_zero(self) -> None:
        process_inventory = {
            "root_app_pids": [111, 222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
            ],
        }
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex\ttrue\tfalse\tfalse\t0\n",
            stderr="",
        )
        with (
            mock.patch("wild_boar_proxy.native_window_probe.subprocess.run", return_value=completed),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_window_presence",
                return_value=(True, "[{'window_owner_name': 'Codex', 'window_number': 9}]"),
            ),
        ):
            packet = native_probe._window_observation_via_ax(process_inventory)

        self.assertTrue(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 222)
        self.assertEqual(packet["window_query_method"], "CGWindowList pid-bound on-screen window")
        self.assertEqual(packet["ax_window_count"], 0)
        self.assertEqual(packet["window_count"], 1)

    def test_window_observation_can_use_fresh_window_lifecycle_scope_when_ax_reports_zero_windows(self) -> None:
        process_inventory = {
            "root_app_pids": [222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
            ],
        }
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex\ttrue\ttrue\tfalse\t0\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            scope_path = (
                profile_dir / "electron-user-data" / "sentry" / "scope_v3.json"
            )
            scope_path.parent.mkdir(parents=True, exist_ok=True)
            scope_path.write_text(
                json.dumps(
                    {
                        "scope": {
                            "breadcrumbs": [
                                {"message": "app.browser-window-created"},
                                {"message": "window.show"},
                                {"message": "app.browser-window-focus"},
                                {
                                    "message": "[window-manager] window ready-to-show appearance=primary hostId=local startupElapsedMs=592 webContentsId=1 windowId=1"
                                },
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.subprocess.run",
                    return_value=completed,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cg_window_presence",
                    return_value=(False, "cg_query_unavailable_pyobjc_framework_quartz_not_installed"),
                ),
            ):
                packet = native_probe._window_observation_packet_for_process_inventory(
                    process_inventory,
                    profile_dir=profile_dir,
                )

        self.assertTrue(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 222)
        self.assertEqual(
            packet["window_query_method"],
            "Electron/Sentry window lifecycle scope",
        )
        self.assertTrue(packet["window_lifecycle_scope_fallback_used"])
        self.assertTrue(
            packet["window_lifecycle_scope_packet"]["window_lifecycle_observed"]
        )

    def test_window_observation_scope_fallback_requires_fresh_window_lifecycle_scope(self) -> None:
        process_inventory = {
            "root_app_pids": [222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
            ],
        }
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex\ttrue\ttrue\tfalse\t0\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir) / "profile"
            scope_path = (
                profile_dir / "electron-user-data" / "sentry" / "scope_v3.json"
            )
            scope_path.parent.mkdir(parents=True, exist_ok=True)
            scope_path.write_text(
                json.dumps(
                    {
                        "scope": {
                            "breadcrumbs": [
                                {"message": "app.browser-window-created"},
                                {"message": "window.show"},
                                {"message": "app.browser-window-focus"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            os.utime(scope_path, (1, 1))
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.subprocess.run",
                    return_value=completed,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cg_window_presence",
                    return_value=(False, "cg_query_unavailable_pyobjc_framework_quartz_not_installed"),
                ),
            ):
                packet = native_probe._window_observation_packet_for_process_inventory(
                    process_inventory,
                    profile_dir=profile_dir,
                )

        self.assertFalse(packet["window_observed"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "pid_visible_but_accessible_window_absent",
        )
        self.assertNotIn("window_lifecycle_scope_fallback_used", packet)

    def test_window_observation_can_bind_same_profile_renderer_pid_after_root_miss(self) -> None:
        process_inventory = {
            "root_app_pids": [111, 222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
            ],
        }
        root_completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex\ttrue\tfalse\tfalse\t0\n",
            stderr="",
        )
        renderer_completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex Helper\ttrue\ttrue\tfalse\t1\t120,80\t1320,820\n",
            stderr="",
        )
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.subprocess.run",
                side_effect=[root_completed, renderer_completed],
            ) as run,
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_window_presence",
                return_value=(False, "cg_query_no_windows_found_for_pid"),
            ),
        ):
            packet = native_probe._window_observation_via_ax(process_inventory)

        self.assertTrue(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 333)
        self.assertEqual(packet["window_candidate_source"], "custom_profile_process")
        self.assertEqual(packet["custom_root_process_pids"], [222])
        self.assertEqual(packet["custom_profile_process_pids"], [222, 333])
        self.assertEqual(packet["custom_window_candidate_pids"], [222, 333])
        self.assertEqual(packet["window_candidate_attempt_count"], 2)
        self.assertIn("unix id is 222", run.call_args_list[0].args[0][2])
        self.assertIn("unix id is 333", run.call_args_list[1].args[0][2])

    def test_window_observation_accepts_helper_only_same_profile_candidate(self) -> None:
        process_inventory = {
            "root_app_pids": [111],
            "custom_process_lines": [
                "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
            ],
            "default_process_lines": [
                "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/me/Library/Application Support/Codex",
            ],
        }
        completed = subprocess.CompletedProcess(
            args=["osascript"],
            returncode=0,
            stdout="Codex Helper\ttrue\ttrue\tfalse\t1\t120,80\t1320,820\n",
            stderr="",
        )
        with mock.patch(
            "wild_boar_proxy.native_window_probe.subprocess.run",
            return_value=completed,
        ) as run:
            packet = native_probe._window_observation_via_ax(process_inventory)

        self.assertTrue(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 333)
        self.assertEqual(packet["custom_root_process_pids"], [])
        self.assertEqual(packet["custom_profile_process_pids"], [333])
        self.assertEqual(packet["default_profile_process_pids"], [111])
        self.assertEqual(packet["custom_window_candidate_pids"], [333])
        self.assertEqual(packet["window_candidate_source"], "custom_profile_process")
        self.assertFalse(packet["browser_cdp_authority_widened"])
        self.assertIn("unix id is 333", run.call_args.args[0][2])

    def test_window_observation_does_not_fallback_to_unbound_root_pid(self) -> None:
        process_inventory = {
            "root_app_pids": [111],
            "custom_process_lines": [],
        }
        packet = native_probe._window_observation_via_ax(process_inventory)

        self.assertFalse(packet["window_observed"])
        self.assertEqual(packet["blocked_reason_class"], "custom_process_pid_not_observed")

    def test_window_observation_wait_polls_after_process_before_failing(self) -> None:
        process_inventory = {
            "root_app_pids": [222],
            "custom_process_lines": [
                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
            ],
        }
        with mock.patch(
            "wild_boar_proxy.native_window_probe._window_observation_via_ax",
            side_effect=[
                {"window_observed": False, "blocked_reason_class": "pid_visible_but_accessible_window_absent"},
                {"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
            ],
        ) as observe:
            packet = native_probe._wait_for_window_observation_via_ax(
                process_inventory,
                timeout_seconds=0.01,
                poll_seconds=0,
            )

        self.assertTrue(packet["window_observed"])
        self.assertEqual(packet["observed_pid"], 222)
        self.assertEqual(packet["window_observation_attempt_count"], 2)
        self.assertGreaterEqual(observe.call_count, 2)

    def test_window_usability_does_not_promote_cg_only_window_to_input_capable(self) -> None:
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "ax_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(False, "ax_fallback_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_input_capable",
                return_value=(False, "cdp_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_input_capable",
                return_value=(True, "[{'window_number': 1}]"),
            ),
        ):
            packet = native_probe._window_usability_from_observation(
                {"window_observed": True, "observed_pid": 222}
            )

        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertFalse(packet["native_window_usable"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "input_capable_ui_not_proven_for_pid_window_present",
        )

    def test_window_usability_accepts_pid_bound_ax_fallback_before_cg(self) -> None:
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "ax_guarded_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(True, "Codex, true"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_input_capable",
                return_value=(True, "[{'window_number': 1}]"),
            ) as cg_probe,
        ):
            packet = native_probe._window_usability_from_observation(
                {"window_observed": True, "observed_pid": 222}
            )

        self.assertTrue(packet["input_capable_ui_observed"])
        self.assertTrue(packet["native_window_usable"])
        self.assertIn("mechanism_0_pid_fallback: Codex, true", packet["ax_query_result"])
        cg_probe.assert_not_called()

    def test_window_usability_accepts_pid_bound_cdp_dom_input_before_cg(self) -> None:
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "ax_guarded_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(False, "ax_fallback_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_input_capable",
                return_value=(
                    True,
                    '{"cdp_port_owner_pids":"222","cdp_visible_input_candidate_count":1,"cdp_text_value_captured":false}',
                ),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_input_capable",
                return_value=(True, "[{'window_number': 1}]"),
            ) as cg_probe,
        ):
            packet = native_probe._window_usability_from_observation(
                {"window_observed": True, "observed_pid": 222}
            )

        self.assertTrue(packet["input_capable_ui_observed"])
        self.assertTrue(packet["native_window_usable"])
        self.assertIn("mechanism_cdp_pid_bound_dom_input", packet["ax_query_result"])
        self.assertEqual(packet["native_app_usability_source"], "cdp_renderer_input_capable_ui")
        self.assertTrue(packet["cdp_localhost_only"])
        self.assertTrue(packet["cdp_endpoint_redacted"])
        self.assertTrue(packet["cdp_target_bound_to_custom_launch"])
        self.assertTrue(packet["cdp_editable_surface_observed"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_ax_tree_exposed"])
        self.assertFalse(packet["browser_cdp_authority_widened"])
        self.assertEqual(
            packet["input_capable_query_method"],
            "CDP localhost launched-renderer DOM/AX editable-surface proof",
        )
        cg_probe.assert_not_called()

    def test_window_usability_reports_cdp_target_without_editable_surface_before_cg(self) -> None:
        cdp_result = json.dumps(
            {
                "cdp_port": 9223,
                "cdp_port_owner_pids": "222",
                "cdp_target_url": "app://-/index.html",
                "cdp_target_type": "page",
                "cdp_ready_state": "complete",
                "cdp_input_candidate_count": 0,
                "cdp_visible_input_candidate_count": 0,
                "cdp_text_value_captured": False,
                "cdp_prompt_attempted": False,
                "cdp_route_trace_bound": False,
            },
            sort_keys=True,
        )
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "ax_guarded_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(False, "ax_fallback_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_input_capable",
                return_value=(False, cdp_result),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_input_capable",
                return_value=(True, "[{'window_number': 1}]"),
            ) as cg_probe,
        ):
            packet = native_probe._window_usability_from_observation(
                {"window_observed": True, "observed_pid": 222}
            )

        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertFalse(packet["native_window_usable"])
        self.assertEqual(packet["blocked_reason_class"], "cdp_renderer_input_surface_not_observed")
        self.assertEqual(
            packet["native_app_usability_source"],
            "cdp_renderer_target_without_editable_surface",
        )
        self.assertTrue(packet["cdp_localhost_only"])
        self.assertTrue(packet["cdp_endpoint_redacted"])
        self.assertTrue(packet["cdp_target_bound_to_custom_launch"])
        self.assertFalse(packet["cdp_editable_surface_observed"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_ax_tree_exposed"])
        self.assertFalse(packet["browser_cdp_authority_widened"])
        self.assertIn("mechanism_cdp_pid_bound_dom_input", packet["ax_query_result"])
        self.assertEqual(
            packet["input_capable_query_method"],
            "CDP localhost launched-renderer target observed, editable surface not proven",
        )
        cg_probe.assert_not_called()

    def test_window_usability_reports_cdp_startup_loader_as_specific_blocker(self) -> None:
        cdp_result = json.dumps(
            {
                "cdp_port": 9223,
                "cdp_port_owner_pids": "222",
                "cdp_target_url": "app://-/index.html",
                "cdp_target_type": "page",
                "cdp_ready_state": "complete",
                "cdp_input_candidate_count": 0,
                "cdp_visible_input_candidate_count": 0,
                "cdp_startup_loader_count": 1,
                "cdp_visible_startup_loader_count": 1,
                "cdp_text_value_captured": False,
                "cdp_prompt_attempted": False,
                "cdp_route_trace_bound": False,
            },
            sort_keys=True,
        )
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "ax_guarded_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(False, "ax_fallback_unavailable"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_input_capable",
                return_value=(False, cdp_result),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cg_input_capable",
                return_value=(True, "[{'window_number': 1}]"),
            ) as cg_probe,
        ):
            packet = native_probe._window_usability_from_observation(
                {"window_observed": True, "observed_pid": 222}
            )

        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertFalse(packet["native_window_usable"])
        self.assertEqual(packet["blocked_reason_class"], "cdp_renderer_startup_loader_stuck")
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "cdp_renderer_startup_loader_stuck",
        )
        self.assertEqual(
            packet["native_app_usability_source"],
            "cdp_renderer_startup_loader_without_editable_surface",
        )
        self.assertTrue(packet["renderer_startup_loader_observed"])
        self.assertFalse(packet["renderer_mounted"])
        self.assertFalse(packet["cdp_editable_surface_observed"])
        self.assertIn("mechanism_cdp_pid_bound_dom_input", packet["ax_query_result"])
        cg_probe.assert_not_called()

    def test_window_usability_reports_cdp_port_owner_mismatch_as_recheckable_blocker(
        self,
    ) -> None:
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable_by_name",
                return_value=(False, "Codex\tCodex\tfalse"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._ax_input_capable",
                return_value=(False, "Codex, false"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_input_capable",
                return_value=(False, "cdp_port_owner_mismatch_or_absent:111,222"),
            ),
            mock.patch("wild_boar_proxy.native_window_probe._cg_input_capable") as cg_probe,
        ):
            packet = native_probe._window_usability_from_observation(
                {
                    "window_observed": True,
                    "observed_pid": 333,
                    "window_visible": True,
                    "custom_window_candidate_pids": [333],
                },
                cdp_port=49231,
            )

        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "cdp_port_owner_mismatch_or_absent",
        )
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "cdp_port_owner_mismatch_or_absent",
        )
        self.assertEqual(
            packet["native_app_usability_source"],
            "cdp_renderer_port_owner_not_bound",
        )
        self.assertTrue(
            native_probe._post_launch_usability_recheck_candidate(packet)
        )
        cg_probe.assert_not_called()

    def test_codex_desktop_auth_blocker_refines_cdp_surface_block_without_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "\n".join(
                    [
                        "DevTools listening on ws://127.0.0.1:9223/devtools/browser/old",
                        "older unrelated stderr",
                        "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current",
                        "Sign in to ChatGPT in Codex Desktop to check remote control authorization.",
                    ]
                ),
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "cdp_renderer_input_surface_not_observed",
                    "native_app_usability_source": "cdp_renderer_target_without_editable_surface",
                    "cdp_localhost_only": True,
                    "cdp_endpoint_redacted": True,
                    "cdp_target_bound_to_custom_launch": True,
                    "cdp_editable_surface_observed": False,
                    "raw_dom_exposed": False,
                    "raw_ax_tree_exposed": False,
                    "browser_cdp_authority_widened": False,
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
            )

        self.assertFalse(packet["native_window_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "codex_desktop_sign_in_required_for_renderer_surface",
        )
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "cdp_renderer_input_surface_not_observed",
        )
        self.assertEqual(packet["native_app_usability_source"], "codex_desktop_auth_blocker")
        self.assertTrue(packet["codex_desktop_auth_blocker_observed"])
        self.assertEqual(
            packet["codex_desktop_auth_error_class"],
            "codex_desktop_remote_control_authorization_sign_in_required",
        )
        self.assertTrue(packet["launcher_stderr_redacted"])
        self.assertFalse(packet["cdp_editable_surface_observed"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_ax_tree_exposed"])
        self.assertFalse(packet["browser_cdp_authority_widened"])

    def test_codex_desktop_auth_blocker_requires_current_launch_stderr_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            stale_stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stale_stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stale_stderr_path.write_text(
                "\n".join(
                    [
                        "DevTools listening on ws://127.0.0.1:9223/devtools/browser/old",
                        "Sign in to ChatGPT in Codex Desktop to check remote control authorization.",
                    ]
                ),
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "cdp_renderer_input_surface_not_observed",
                    "native_app_usability_source": "cdp_renderer_target_without_editable_surface",
                    "cdp_localhost_only": True,
                    "cdp_endpoint_redacted": True,
                    "cdp_target_bound_to_custom_launch": True,
                    "cdp_editable_surface_observed": False,
                    "raw_dom_exposed": False,
                    "raw_ax_tree_exposed": False,
                    "browser_cdp_authority_widened": False,
                },
                profile_dir=profile_dir,
            )

        self.assertNotIn("codex_desktop_auth_blocker_observed", packet)
        self.assertEqual(
            packet["blocked_reason_class"],
            "cdp_renderer_input_surface_not_observed",
        )

    def test_codex_desktop_auth_blocker_refines_missing_window_block_without_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "\n".join(
                    [
                        "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current",
                        "Sign in to ChatGPT in Codex Desktop to check remote control authorization.",
                    ]
                ),
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    "native_app_usability_source": "not_proven",
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
            )

        self.assertFalse(packet["native_window_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "codex_desktop_sign_in_required_for_renderer_surface",
        )
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "input_capable_window_not_proven_for_pid",
        )
        self.assertEqual(packet["native_app_usability_source"], "codex_desktop_auth_blocker")
        self.assertTrue(packet["codex_desktop_auth_blocker_observed"])
        self.assertTrue(packet["launcher_stderr_redacted"])

    def test_codex_desktop_auth_blocker_has_specific_launch_machine_code(self) -> None:
        machine_error_code = native_probe._custom_native_launch_blocked_machine_error(
            launcher_failed_before_process=False,
            process_started=True,
            process_still_alive=True,
            custom_window_visible=False,
            native_app_usable=False,
            desktop_auth_blocker=True,
            renderer_surface_blocked_reason="input_capable_window_not_proven_for_pid",
        )

        self.assertEqual(
            machine_error_code,
            "CUSTOM_NATIVE_CODEX_DESKTOP_AUTH_REQUIRED",
        )

    def test_codex_desktop_process_exit_beats_auth_blocker_machine_code(self) -> None:
        machine_error_code = native_probe._custom_native_launch_blocked_machine_error(
            launcher_failed_before_process=False,
            process_started=True,
            process_still_alive=False,
            custom_window_visible=False,
            native_app_usable=False,
            desktop_auth_blocker=True,
            renderer_surface_blocked_reason="input_capable_window_not_proven_for_pid",
        )

        self.assertEqual(
            machine_error_code,
            "CUSTOM_NATIVE_PROCESS_EXITED_AFTER_START",
        )

    def test_codex_desktop_process_exit_beats_auth_blocker_human_message(self) -> None:
        human_message = native_probe._custom_native_launch_blocked_human_message(
            launcher_failed_before_process=False,
            process_started=True,
            process_still_alive=False,
            custom_window_visible=False,
            native_app_usable=False,
            desktop_auth_blocker=True,
            renderer_surface_blocked_reason="input_capable_window_not_proven_for_pid",
        )

        self.assertIn("then exited", human_message)
        self.assertNotIn("sign-in is required", human_message)

    def test_codex_desktop_auth_blocker_detects_no_token_auth_401(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "\n".join(
                    [
                        "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current",
                        '[electron-fetch-wrapper] desktop_fetch_auth_401 hadToken=false skipRetryReason=no_token_attached target="GET https://chatgpt.com/backend-api/wham/tasks/list"',
                    ]
                ),
                encoding="utf-8",
            )
            packet = native_probe._codex_desktop_auth_blocker_from_profile(
                profile_dir,
                launcher_stderr_path=stderr_path,
            )

        self.assertTrue(packet["codex_desktop_auth_blocker_observed"])
        self.assertEqual(
            packet["codex_desktop_auth_blocked_reason_class"],
            "codex_desktop_sign_in_required_for_renderer_surface",
        )
        self.assertEqual(
            packet["codex_desktop_auth_error_class"],
            "codex_desktop_chatgpt_auth_token_missing",
        )

    def test_codex_desktop_auth_blocker_bounded_recheck_catches_late_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current\n",
                encoding="utf-8",
            )

            def write_late_marker(_seconds: float) -> None:
                stderr_path.write_text(
                    "\n".join(
                        [
                            "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current",
                            '[electron-fetch-wrapper] desktop_fetch_auth_401 hadToken=false skipRetryReason=no_token_attached target="GET https://chatgpt.com/backend-api/wham/tasks/list"',
                        ]
                    ),
                    encoding="utf-8",
                )

            with mock.patch.object(native_probe.time, "sleep", side_effect=write_late_marker):
                packet = native_probe._bounded_recheck_codex_desktop_auth_blocker(
                    {
                        "native_window_usable": False,
                        "input_capable_ui_observed": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                        "native_app_usability_source": "not_proven",
                    },
                    profile_dir=profile_dir,
                    launcher_stderr_path=stderr_path,
                )

        self.assertTrue(packet["codex_desktop_auth_blocker_observed"])
        self.assertEqual(
            packet["blocked_reason_class"],
            "codex_desktop_sign_in_required_for_renderer_surface",
        )

    def test_codex_desktop_auth_state_fallback_refines_missing_profile_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            (profile_dir / "home").mkdir(parents=True, exist_ok=True)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current\n",
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    "native_app_usability_source": "not_proven",
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
                allow_profile_auth_state_fallback=True,
                profile_auth_state_fallback_allowed_by_current_launch=True,
            )

        self.assertTrue(packet["codex_desktop_auth_blocker_observed"])
        self.assertEqual(
            packet["codex_desktop_auth_error_class"],
            "codex_desktop_custom_profile_chatgpt_auth_state_missing",
        )
        self.assertEqual(packet["native_app_usability_source"], "codex_desktop_auth_blocker")
        self.assertTrue(packet["desktop_auth_state_path_redacted"])

    def test_codex_desktop_auth_state_fallback_requires_current_launch_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            (profile_dir / "home").mkdir(parents=True, exist_ok=True)
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current\n",
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    "native_app_usability_source": "not_proven",
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
                allow_profile_auth_state_fallback=True,
            )

        self.assertNotIn("codex_desktop_auth_blocker_observed", packet)
        self.assertEqual(packet["blocked_reason_class"], "input_capable_window_not_proven_for_pid")

    def test_codex_desktop_auth_state_fallback_does_not_override_present_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            auth_path = (
                profile_dir
                / "home"
                / "Library"
                / "Application Support"
                / "Codex"
                / "auth.json"
            )
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth_path.write_text("{}", encoding="utf-8")
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current\n",
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    "native_app_usability_source": "not_proven",
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
                allow_profile_auth_state_fallback=True,
                profile_auth_state_fallback_allowed_by_current_launch=True,
            )

        self.assertNotIn("codex_desktop_auth_blocker_observed", packet)
        self.assertEqual(packet["blocked_reason_class"], "input_capable_window_not_proven_for_pid")

    def test_codex_desktop_auth_state_fallback_skips_chatgpt_blocker_for_api_key_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_dir = Path(temp_dir)
            (profile_dir / "home").mkdir(parents=True, exist_ok=True)
            (profile_dir / "auth.json").write_text(
                json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "local-token"}) + "\n",
                encoding="utf-8",
            )
            stderr_path = profile_dir / "tmp" / "launcher.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "DevTools listening on ws://127.0.0.1:9223/devtools/browser/current\n",
                encoding="utf-8",
            )
            packet = native_probe._apply_codex_desktop_auth_blocker(
                {
                    "native_window_usable": False,
                    "input_capable_ui_observed": False,
                    "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    "native_app_usability_source": "not_proven",
                },
                profile_dir=profile_dir,
                launcher_stderr_path=stderr_path,
                allow_profile_auth_state_fallback=True,
                profile_auth_state_fallback_allowed_by_current_launch=True,
            )

        self.assertNotIn("codex_desktop_auth_blocker_observed", packet)
        self.assertEqual(packet["blocked_reason_class"], "input_capable_window_not_proven_for_pid")

    def test_cdp_input_capable_blocks_when_debug_port_not_owned_by_pid(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
            return_value=(False, "999"),
        ):
            input_capable, result = native_probe._cdp_input_capable(222, port=9223)

        self.assertFalse(input_capable)
        self.assertIn("cdp_port_owner_mismatch_or_absent", result)

    def test_cdp_input_capable_blocks_non_app_page_target(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = json.dumps([
            {
                "type": "page",
                "url": "https://example.invalid/",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
            }
        ]).encode("utf-8")
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch("wild_boar_proxy.native_window_probe.urllib.request.urlopen", return_value=response),
        ):
            input_capable, result = native_probe._cdp_input_capable(222, port=9223)

        self.assertFalse(input_capable)
        self.assertEqual(result, "cdp_app_page_target_not_found")

    def test_cdp_input_capable_blocks_app_page_without_visible_editable_surface(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = json.dumps([
            {
                "type": "page",
                "url": "app://-/index.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
            }
        ]).encode("utf-8")
        cdp_packet = {
            "id": 1,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 0,
                        "visibleInputCandidateCount": 0,
                        "textValueCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch("wild_boar_proxy.native_window_probe.urllib.request.urlopen", return_value=response),
            mock.patch("wild_boar_proxy.native_window_probe._cdp_command", return_value=cdp_packet),
        ):
            input_capable, result = native_probe._cdp_input_capable(222, port=9223)

        self.assertFalse(input_capable)
        bounded = json.loads(result)
        self.assertEqual(bounded["cdp_target_url"], "app://-/index.html")
        self.assertEqual(bounded["cdp_page_target_count"], 1)
        self.assertEqual(bounded["cdp_ready_state"], "complete")
        self.assertEqual(bounded["cdp_visible_input_candidate_count"], 0)
        self.assertFalse(bounded["cdp_text_value_captured"])
        self.assertFalse(bounded["cdp_prompt_attempted"])
        self.assertFalse(bounded["cdp_route_trace_bound"])

    def test_cdp_input_capable_accepts_visible_editable_surface_without_raw_dom(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = json.dumps([
            {
                "type": "page",
                "url": "app://-/index.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
            }
        ]).encode("utf-8")
        cdp_packet = {
            "id": 1,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "textValueCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch("wild_boar_proxy.native_window_probe.urllib.request.urlopen", return_value=response),
            mock.patch("wild_boar_proxy.native_window_probe._cdp_command", return_value=cdp_packet),
        ):
            input_capable, result = native_probe._cdp_input_capable(222, port=9223)

        self.assertTrue(input_capable)
        bounded = json.loads(result)
        self.assertEqual(bounded["cdp_page_target_count"], 1)
        self.assertEqual(bounded["cdp_visible_input_candidate_count"], 1)
        self.assertFalse(bounded["cdp_text_value_captured"])
        self.assertFalse(bounded["cdp_prompt_attempted"])
        self.assertFalse(bounded["cdp_route_trace_bound"])

    def test_cdp_input_capable_accepts_port_owner_from_same_profile_candidate_pids(self) -> None:
        lsof_completed = subprocess.CompletedProcess(
            args=["lsof"],
            returncode=0,
            stdout="333\n",
            stderr="",
        )
        cdp_packet = {
            "id": 1,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "textValueCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.subprocess.run",
                return_value=lsof_completed,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                return_value=cdp_packet,
            ),
        ):
            input_capable, result = native_probe._cdp_input_capable(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertTrue(input_capable)
        bounded = json.loads(result)
        self.assertEqual(bounded["cdp_port_owner_pids"], "333")
        self.assertEqual(bounded["cdp_allowed_owner_pids"], [222, 333])
        self.assertTrue(bounded["cdp_port_owner_bound_to_custom_profile"])
        self.assertFalse(bounded["browser_cdp_authority_widened"])

    def test_cdp_voice_icon_observation_accepts_native_mic_affordance_without_raw_dom(self) -> None:
        cdp_packet = {
            "id": 5001,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "composerContainerCandidateCount": 1,
                        "buttonCandidateCount": 4,
                        "visibleButtonCandidateCount": 3,
                        "semanticVoiceCandidateCount": 1,
                        "composerBoundVoiceCandidateCount": 1,
                        "forbiddenVoiceCandidateCount": 0,
                        "localForbiddenVoiceContextCount": 0,
                        "dedicatedVoiceCandidateCount": 1,
                        "nativeVoiceCandidateCount": 1,
                        "visibleNativeVoiceCandidateCount": 1,
                        "voiceDetectorHintCount": 11,
                        "semanticAttributeScanPerformed": True,
                        "domTextContentScanned": False,
                        "textValueCaptured": False,
                        "rawLabelCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "333"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                return_value=cdp_packet,
            ) as cdp_command,
        ):
            packet = native_probe._cdp_voice_icon_observation(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["native_voice_icon_observed"])
        self.assertTrue(packet["microphone_permission_check_required"])
        self.assertFalse(packet["native_voice_shortcut_tested"])
        self.assertFalse(packet["native_voice_shortcut_available"])
        self.assertEqual(packet["voice_shortcut_blocked_reason_code"], "VOICE_SHORTCUT_NOT_TESTED_NO_UI_MUTATION")
        self.assertEqual(packet["cdp_allowed_owner_pids"], [222, 333])
        self.assertTrue(packet["cdp_port_owner_bound_to_custom_profile"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_ax_tree_exposed"])
        self.assertFalse(packet["raw_label_recorded"])
        self.assertTrue(packet["semantic_attribute_scan_performed"])
        self.assertFalse(packet["dom_text_content_scanned"])
        self.assertEqual(packet["visible_input_candidate_count"], 1)
        self.assertEqual(packet["composer_container_candidate_count"], 1)
        self.assertEqual(packet["semantic_voice_candidate_count"], 1)
        self.assertEqual(packet["composer_bound_voice_candidate_count"], 1)
        self.assertEqual(packet["forbidden_voice_candidate_count"], 0)
        self.assertEqual(packet["local_forbidden_voice_context_count"], 0)
        self.assertEqual(packet["dedicated_voice_candidate_count"], 1)
        self.assertTrue(packet["no_secret_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertTrue(packet["does_not_patch_codex_ui"])
        self.assertTrue(packet["voice_is_not_locally_imitated"])
        expression = cdp_command.call_args.args[1]["params"]["expression"]
        self.assertIn("microphone", expression)
        self.assertIn("composerContainers", expression)
        self.assertIn("buttonIsInComposerContainer", expression)
        self.assertIn("buttonLooksIconSized", expression)
        self.assertIn("hasForbiddenVoiceContext", expression)
        self.assertIn("buttonHasForbiddenLocalContext", expression)
        self.assertNotIn("innerText", expression)
        self.assertNotIn("textContent", expression)
        self.assertNotIn("OPENAI_API_KEY", expression)

    def test_cdp_voice_icon_observation_blocks_without_native_mic_affordance(self) -> None:
        cdp_packet = {
            "id": 5001,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "composerContainerCandidateCount": 1,
                        "buttonCandidateCount": 4,
                        "visibleButtonCandidateCount": 3,
                        "semanticVoiceCandidateCount": 0,
                        "composerBoundVoiceCandidateCount": 0,
                        "forbiddenVoiceCandidateCount": 0,
                        "localForbiddenVoiceContextCount": 0,
                        "dedicatedVoiceCandidateCount": 0,
                        "nativeVoiceCandidateCount": 0,
                        "visibleNativeVoiceCandidateCount": 0,
                        "voiceDetectorHintCount": 11,
                        "semanticAttributeScanPerformed": True,
                        "domTextContentScanned": False,
                        "textValueCaptured": False,
                        "rawLabelCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "333"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                return_value=cdp_packet,
            ),
        ):
            packet = native_probe._cdp_voice_icon_observation(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_VOICE_ICON_NOT_OBSERVED")
        self.assertFalse(packet["native_voice_icon_observed"])
        self.assertEqual(packet["visible_native_voice_candidate_count"], 0)
        self.assertEqual(packet["voice_blocked_reason_code"], "NATIVE_VOICE_ICON_NOT_OBSERVED")
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_label_recorded"])
        self.assertTrue(packet["no_secret_exposed"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertFalse(packet["raw_backend_details_exposed"])
        self.assertTrue(packet["semantic_attribute_scan_performed"])
        self.assertFalse(packet["dom_text_content_scanned"])

    def test_cdp_voice_icon_observation_blocks_semantic_voice_button_not_dedicated_to_composer(self) -> None:
        cdp_packet = {
            "id": 5001,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "composerContainerCandidateCount": 1,
                        "buttonCandidateCount": 4,
                        "visibleButtonCandidateCount": 3,
                        "semanticVoiceCandidateCount": 1,
                        "composerBoundVoiceCandidateCount": 0,
                        "forbiddenVoiceCandidateCount": 1,
                        "localForbiddenVoiceContextCount": 1,
                        "dedicatedVoiceCandidateCount": 0,
                        "nativeVoiceCandidateCount": 0,
                        "visibleNativeVoiceCandidateCount": 0,
                        "voiceDetectorHintCount": 11,
                        "semanticAttributeScanPerformed": True,
                        "domTextContentScanned": False,
                        "textValueCaptured": False,
                        "rawLabelCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "333"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                return_value=cdp_packet,
            ),
        ):
            packet = native_probe._cdp_voice_icon_observation(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_VOICE_ICON_DEDICATED_CONTROL_NOT_OBSERVED",
        )
        self.assertFalse(packet["native_voice_icon_observed"])
        self.assertEqual(packet["semantic_voice_candidate_count"], 1)
        self.assertEqual(packet["composer_bound_voice_candidate_count"], 0)
        self.assertEqual(packet["forbidden_voice_candidate_count"], 1)
        self.assertEqual(packet["local_forbidden_voice_context_count"], 1)
        self.assertEqual(packet["dedicated_voice_candidate_count"], 0)
        self.assertEqual(packet["visible_native_voice_candidate_count"], 0)
        self.assertEqual(
            packet["voice_blocked_reason_code"],
            "NATIVE_VOICE_ICON_DEDICATED_CONTROL_NOT_OBSERVED",
        )

    def test_cdp_voice_icon_observation_blocks_voice_button_with_forbidden_local_context(self) -> None:
        cdp_packet = {
            "id": 5001,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "composerContainerCandidateCount": 1,
                        "buttonCandidateCount": 5,
                        "visibleButtonCandidateCount": 4,
                        "semanticVoiceCandidateCount": 1,
                        "composerBoundVoiceCandidateCount": 0,
                        "forbiddenVoiceCandidateCount": 0,
                        "localForbiddenVoiceContextCount": 1,
                        "dedicatedVoiceCandidateCount": 0,
                        "nativeVoiceCandidateCount": 0,
                        "visibleNativeVoiceCandidateCount": 0,
                        "voiceDetectorHintCount": 11,
                        "semanticAttributeScanPerformed": True,
                        "domTextContentScanned": False,
                        "textValueCaptured": False,
                        "rawLabelCaptured": False,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "333"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                return_value=cdp_packet,
            ),
        ):
            packet = native_probe._cdp_voice_icon_observation(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_VOICE_ICON_DEDICATED_CONTROL_NOT_OBSERVED",
        )
        self.assertFalse(packet["native_voice_icon_observed"])
        self.assertEqual(packet["semantic_voice_candidate_count"], 1)
        self.assertEqual(packet["composer_bound_voice_candidate_count"], 0)
        self.assertEqual(packet["forbidden_voice_candidate_count"], 0)
        self.assertEqual(packet["local_forbidden_voice_context_count"], 1)
        self.assertEqual(packet["dedicated_voice_candidate_count"], 0)

    def test_cdp_voice_icon_observation_blocks_when_debug_port_not_bound_to_custom_pid(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
            return_value=(False, "999"),
        ):
            packet = native_probe._cdp_voice_icon_observation(
                222,
                port=9223,
                allowed_owner_pids=[222, 333],
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CDP_PORT_OWNER_MISMATCH_OR_ABSENT")
        self.assertFalse(packet["native_voice_icon_observed"])
        self.assertFalse(packet["cdp_port_owner_bound_to_custom_profile"])
        self.assertTrue(packet["cdp_localhost_only"])
        self.assertTrue(packet["cdp_endpoint_redacted"])
        self.assertFalse(packet["browser_cdp_authority_widened"])

    def test_cdp_prompt_submit_inserts_and_submits_without_raw_prompt_readback(self) -> None:
        cdp_packets = [
            {
                "id": 3001,
                "result": {
                    "result": {
                        "value": {
                            "focused": True,
                            "readyState": "complete",
                            "url": "app://-/index.html",
                            "inputCandidateCount": 1,
                            "visibleInputCandidateCount": 1,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {"id": 3101, "result": {}},
            {
                "id": 3201,
                "result": {
                    "result": {
                        "value": {
                            "inputFocused": True,
                            "insertedLengthMatches": True,
                            "insertedLength": 11,
                            "expectedLength": 11,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3301,
                "result": {
                    "result": {
                        "value": {
                            "submitted": True,
                            "submitButtonObserved": True,
                            "submitMechanism": "cdp_button_click",
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3650,
                "result": {
                    "result": {
                        "value": {
                            "promptAcceptanceScanPerformed": True,
                            "promptAccepted": True,
                            "promptStillInInput": False,
                            "inputCandidateCount": 1,
                            "inputContainingPromptCandidateCount": 0,
                            "maxVisibleInputLength": 0,
                            "disabledSubmitLikeButtonCount": 0,
                            "submitLikeButtonCount": 1,
                            "textValueCaptured": False,
                            "rawDomExposed": False,
                            "rawPromptRecorded": False,
                        }
                    }
                },
            },
        ]
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=cdp_packets,
            ) as cdp_command,
        ):
            packet = native_probe._cdp_submit_prompt_to_app_page(
                222,
                "hello world",
                request_id="native-submit-ok",
                port=9223,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["input_text_insert_attempted"])
        self.assertTrue(packet["input_text_insert_succeeded"])
        self.assertTrue(packet["prompt_submitted"])
        self.assertTrue(packet["native_prompt_turn_accepted"])
        self.assertFalse(packet["native_prompt_still_in_input"])
        self.assertEqual(packet["submit_mechanism"], "cdp_button_click")
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["native_agent_provider_call_directly_observed"])
        self.assertFalse(packet["custom_codex_response_text_read_proven"])
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN",
        )
        self.assertFalse(packet["secret_value_exposed"])
        self.assertEqual(cdp_command.call_count, 5)

    def test_cdp_prompt_submit_observes_exact_response_token_without_raw_text(self) -> None:
        cdp_packets = [
            {
                "id": 3001,
                "result": {
                    "result": {
                        "value": {
                            "focused": True,
                            "readyState": "complete",
                            "url": "app://-/index.html",
                            "inputCandidateCount": 1,
                            "visibleInputCandidateCount": 1,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {"id": 3101, "result": {}},
            {
                "id": 3201,
                "result": {
                    "result": {
                        "value": {
                            "inputFocused": True,
                            "insertedLengthMatches": True,
                            "insertedLength": 11,
                            "expectedLength": 11,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3301,
                "result": {
                    "result": {
                        "value": {
                            "submitted": True,
                            "submitButtonObserved": True,
                            "submitMechanism": "cdp_button_click",
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3650,
                "result": {
                    "result": {
                        "value": {
                            "promptAcceptanceScanPerformed": True,
                            "promptAccepted": True,
                            "promptStillInInput": False,
                            "inputCandidateCount": 1,
                            "inputContainingPromptCandidateCount": 0,
                            "maxVisibleInputLength": 0,
                            "disabledSubmitLikeButtonCount": 0,
                            "submitLikeButtonCount": 1,
                            "textValueCaptured": False,
                            "rawDomExposed": False,
                            "rawPromptRecorded": False,
                        }
                    }
                },
            },
            {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": True,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "responseSurfaceCandidateCount": 1,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 1,
                            "responseLikeCandidateCount": 1,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": True,
                            "customResponseBoundToRequest": True,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": True,
                            "textValueCaptured": False,
                            "rawDomExposed": False,
                            "rawPromptRecorded": False,
                        }
                    }
                },
            },
        ]
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=cdp_packets,
            ) as cdp_command,
        ):
            packet = native_probe._cdp_submit_prompt_to_app_page(
                222,
                "hello world",
                request_id="native-submit-response-ok",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-response-ok",
                port=9223,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["prompt_submitted"])
        self.assertTrue(packet["native_prompt_turn_accepted"])
        self.assertFalse(packet["native_agent_provider_call_directly_observed"])
        self.assertTrue(packet["custom_codex_response_text_read_proven"])
        self.assertTrue(packet["custom_response_exact_token_observed"])
        self.assertTrue(packet["custom_response_bound_to_request"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertTrue(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(packet["native_free_text_observer_machine_error_code"], "OK")
        self.assertTrue(packet["custom_response_observer_attempted"])
        self.assertTrue(packet["custom_response_observer_scan_performed"])
        self.assertTrue(packet["assistant_turn_probe_attempted"])
        self.assertTrue(packet["assistant_turn_probe_scan_performed"])
        self.assertTrue(packet["assistant_turn_activity_observed"])
        self.assertTrue(packet["assistant_turn_started_observed"])
        self.assertTrue(packet["assistant_turn_completed_observed"])
        self.assertTrue(packet["assistant_turn_activity_ended_observed"])
        self.assertTrue(packet["assistant_turn_post_completion_scan_performed"])
        self.assertFalse(packet["assistant_turn_failed_observed"])
        self.assertEqual(packet["assistant_turn_machine_error_code"], "OK")
        self.assertTrue(packet["custom_response_text_read_without_storing"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_prompt_recorded"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("hello world", serialized)
        self.assertNotIn("WBP_NATIVE_RESPONSE_OK_native-submit-response-ok", serialized)
        self.assertEqual(cdp_command.call_count, 6)
        observer_expression = cdp_command.call_args_list[-1].args[1]["params"]["expression"]
        self.assertTrue(observer_expression.startswith("(async () => {"))
        self.assertIn("requestBindingTexts", observer_expression)
        self.assertIn('"native-submit-response-ok"', observer_expression)
        self.assertIn('"native_submit_response_ok"', observer_expression)
        self.assertIn("expectedText.includes(bindingText)", observer_expression)
        self.assertNotIn("progressCandidateCount > 0", observer_expression)
        self.assertNotIn("requestId,\n    'expected_token'", observer_expression)
        self.assertNotIn("'model',", observer_expression)
        self.assertNotIn("'runtime',", observer_expression)
        acceptance_params = [
            call.args[1]["params"]
            for call in cdp_command.call_args_list
            if call.args[1].get("id") == 3650
        ]
        self.assertTrue(acceptance_params)
        self.assertTrue(
            all(params.get("awaitPromise") is True for params in acceptance_params)
        )
        observer_params = cdp_command.call_args_list[-1].args[1]["params"]
        self.assertTrue(observer_params.get("awaitPromise"))

    def test_cdp_response_observer_exports_bounded_hashed_candidate_map(self) -> None:
        expected_text = "WBP_NATIVE_RESPONSE_OK_native-submit-candidate-map"
        text_sha256 = "a" * 64
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 0,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 1,
                            "promptSuffixEchoCandidateCount": 1,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                            "responseCandidateMapTotalCount": 1,
                            "responseCandidateMapTruncated": False,
                            "responseCandidateMap": [
                                {
                                    "candidateKind": "prompt_echo",
                                    "tagName": "DIV<script>",
                                    "role": "article",
                                    "textSha256": text_sha256,
                                    "textLength": 72,
                                    "lineCount": 2,
                                    "childCount": 0,
                                    "containsExpectedText": True,
                                    "containsRequestId": True,
                                    "containsPromptMarker": True,
                                    "promptEcho": True,
                                    "promptSuffixEcho": True,
                                    "exactToken": False,
                                    "responseLike": False,
                                    "responseSurface": False,
                                    "insideButton": False,
                                    "visibleChildContainsExpected": False,
                                    "expectedTextOffsetClass": "suffix",
                                    "bounds": {
                                        "x": 12,
                                        "y": 34,
                                        "width": 560,
                                        "height": 44,
                                    },
                                    "rawText": expected_text,
                                    "selector": "#raw-secret-selector",
                                }
                            ],
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text=expected_text,
                request_id="native-submit-candidate-map",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["custom_response_candidate_map_available"])
        self.assertEqual(packet["custom_response_candidate_map_candidate_count"], 1)
        self.assertFalse(packet["custom_response_candidate_map_truncated"])
        candidate = packet["custom_response_candidate_map"][0]
        self.assertEqual(candidate["candidate_kind"], "prompt_echo")
        self.assertEqual(candidate["tag_name"], "divscript")
        self.assertEqual(candidate["role"], "article")
        self.assertEqual(candidate["text_sha256"], text_sha256)
        self.assertTrue(candidate["prompt_echo"])
        self.assertTrue(candidate["prompt_suffix_echo"])
        self.assertFalse(candidate["response_like"])
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(expected_text, serialized)
        self.assertNotIn("rawText", serialized)
        self.assertNotIn("selector", serialized)
        self.assertNotIn("raw-secret-selector", serialized)
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["text_value_captured"])

    def test_session_external_route_observer_proves_exact_custom_response_without_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_root = Path(temp_dir)
            session_dir = profile_root / "sessions" / "2026" / "06" / "30"
            session_dir.mkdir(parents=True)
            request_id = "native-session-route-ok"
            prompt = f"DIP: ответь ровно WBP_SESSION_ROUTE_OK_{request_id}"
            expected_text = f"WBP_SESSION_ROUTE_OK_{request_id}"
            session_path = session_dir / "thread.jsonl"
            rows = [
                {
                    "timestamp": "2026-06-30T05:00:36.467Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt + "\n"}],
                    },
                },
                {
                    "timestamp": "2026-06-30T05:00:40.573Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "exec_command",
                        "arguments": "{\"cmd\":\"router-hook auto-route-output --prompt-file -\"}",
                    },
                },
                {
                    "timestamp": "2026-06-30T05:00:50.282Z",
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": expected_text},
                },
                {
                    "timestamp": "2026-06-30T05:00:50.282Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "id": "msg_wbp_external_route",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": expected_text}],
                    },
                },
                {
                    "timestamp": "2026-06-30T05:00:50.292Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": expected_text,
                    },
                },
            ]
            session_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
                encoding="utf-8",
            )

            packet = native_probe._custom_session_external_route_response_observer_packet(
                profile_root=profile_root,
                prompt=prompt,
                request_id=request_id,
                expected_text=expected_text,
                submitted_after_epoch_seconds=time.time() - 5,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["custom_session_prompt_digest_bound"])
        self.assertTrue(packet["custom_session_external_route_message_observed"])
        self.assertTrue(packet["custom_session_task_complete_observed"])
        self.assertTrue(packet["custom_response_exact_token_observed"])
        self.assertTrue(packet["custom_response_bound_to_request"])
        self.assertTrue(packet["native_codex_subagent_absence_proven"])
        self.assertTrue(packet["custom_session_router_command_attempted"])
        self.assertEqual(
            packet["native_free_text_observer_source"],
            "custom_session_jsonl_external_route",
        )
        serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(prompt, serialized)
        self.assertNotIn(expected_text, serialized)
        self.assertFalse(packet["raw_prompt_recorded"])

    def test_cdp_prompt_submit_blocks_when_prompt_stays_in_input_after_click(self) -> None:
        cdp_packets = [
            {
                "id": 3001,
                "result": {
                    "result": {
                        "value": {
                            "focused": True,
                            "readyState": "complete",
                            "url": "app://-/index.html",
                            "inputCandidateCount": 1,
                            "visibleInputCandidateCount": 1,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {"id": 3101, "result": {}},
            {
                "id": 3201,
                "result": {
                    "result": {
                        "value": {
                            "inputFocused": True,
                            "insertedLengthMatches": True,
                            "insertedLength": 11,
                            "expectedLength": 11,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3301,
                "result": {
                    "result": {
                        "value": {
                            "submitted": True,
                            "submitButtonObserved": True,
                            "submitMechanism": "cdp_button_click",
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3650,
                "result": {
                    "result": {
                        "value": {
                            "promptAcceptanceScanPerformed": True,
                            "promptAccepted": False,
                            "promptStillInInput": True,
                            "inputCandidateCount": 1,
                            "inputContainingPromptCandidateCount": 1,
                            "maxVisibleInputLength": 11,
                            "disabledSubmitLikeButtonCount": 0,
                            "submitLikeButtonCount": 1,
                            "textValueCaptured": False,
                            "rawDomExposed": False,
                            "rawPromptRecorded": False,
                        }
                    }
                },
            },
            {
                "id": 3626,
                "result": {
                    "result": {
                        "value": {
                            "submitted": True,
                            "submitButtonObserved": False,
                            "submitMechanism": "cdp_keyboard_event_enter",
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3650,
                "result": {
                    "result": {
                        "value": {
                            "promptAcceptanceScanPerformed": True,
                            "promptAccepted": False,
                            "promptStillInInput": True,
                            "inputCandidateCount": 1,
                            "inputContainingPromptCandidateCount": 1,
                            "maxVisibleInputLength": 11,
                            "disabledSubmitLikeButtonCount": 0,
                            "submitLikeButtonCount": 1,
                            "textValueCaptured": False,
                            "rawDomExposed": False,
                            "rawPromptRecorded": False,
                        }
                    }
                },
            },
        ]
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_app_page_targets",
                return_value=([
                    {
                        "type": "page",
                        "url": "app://-/index.html",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                    }
                ], ""),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe.CUSTOM_NATIVE_PROMPT_ACCEPTANCE_WAIT_SECONDS",
                0.0,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=cdp_packets,
            ) as cdp_command,
        ):
            packet = native_probe._cdp_submit_prompt_to_app_page(
                222,
                "hello world",
                request_id="native-submit-not-accepted",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-not-accepted",
                port=9223,
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_PROMPT_NOT_ACCEPTED_BY_CODEX_FLOW",
        )
        self.assertTrue(packet["input_text_insert_attempted"])
        self.assertTrue(packet["input_text_insert_succeeded"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["native_prompt_turn_accepted"])
        self.assertTrue(packet["native_prompt_still_in_input"])
        self.assertEqual(
            packet["native_prompt_acceptance_input_containing_prompt_candidate_count"],
            1,
        )
        self.assertEqual(
            packet["submit_mechanism"],
            "cdp_button_click+cdp_keyboard_event_enter",
        )
        self.assertFalse(packet["custom_codex_response_text_read_proven"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertEqual(cdp_command.call_count, 7)

    def test_cdp_response_observer_blocks_subagent_marker(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": True,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "responseSurfaceCandidateCount": 1,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 1,
                            "responseLikeCandidateCount": 1,
                            "subagentMarkerCandidateCount": 1,
                            "customResponseExactTokenObserved": True,
                            "customResponseBoundToRequest": True,
                            "nativeCodexSubagentUsedAsDip": True,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-subagent",
                request_id="native-submit-subagent",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["custom_codex_response_text_read_proven"])
        self.assertTrue(packet["custom_response_exact_token_observed"])
        self.assertTrue(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_CODEX_SUBAGENT_USED_AS_DIP",
        )

    def test_cdp_response_observer_blocks_unbound_exact_token(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": True,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "responseSurfaceCandidateCount": 1,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 1,
                            "responseLikeCandidateCount": 1,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": True,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": True,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK",
                request_id="native-submit-stale-token",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["custom_codex_response_text_read_proven"])
        self.assertTrue(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertTrue(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN",
        )

    def test_cdp_response_observer_blocks_prompt_echo_without_response_token(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "responseSurfaceCandidateCount": 0,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 1,
                            "promptSuffixEchoCandidateCount": 1,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-echo",
                request_id="native-submit-echo",
                timeout_seconds=0.1,
            )

        self.assertFalse(packet["custom_codex_response_text_read_proven"])
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertTrue(packet["custom_response_text_read_without_storing"])
        self.assertFalse(packet["assistant_turn_completed_observed"])
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY",
        )
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(packet["custom_response_prompt_suffix_echo_candidate_count"], 1)
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN",
        )

    def test_cdp_response_observer_does_not_treat_generic_progress_as_turn_started(
        self,
    ) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 3,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 7,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-progress",
                request_id="native-submit-progress",
                timeout_seconds=0.1,
            )

        self.assertFalse(packet["assistant_turn_started_observed"])
        self.assertFalse(packet["assistant_turn_completed_observed"])
        self.assertEqual(packet["assistant_turn_progress_candidate_count"], 3)
        self.assertEqual(packet["assistant_turn_stop_generating_candidate_count"], 0)
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED",
        )
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet["raw_dom_exposed"])
        self.assertFalse(packet["raw_prompt_recorded"])

    def test_cdp_response_observer_reports_stop_button_as_turn_still_running(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe._cdp_command",
            return_value={
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 1,
                            "responseSurfaceCandidateCount": 2,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-still-running",
                request_id="native-submit-still-running",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["assistant_turn_activity_observed"])
        self.assertTrue(packet["assistant_turn_started_observed"])
        self.assertFalse(packet["assistant_turn_completed_observed"])
        self.assertFalse(packet["assistant_turn_activity_ended_observed"])
        self.assertFalse(packet["assistant_turn_post_completion_scan_performed"])
        self.assertTrue(packet["assistant_turn_last_scan_active"])
        self.assertEqual(packet["assistant_turn_stop_generating_candidate_count"], 1)
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_STILL_RUNNING",
        )
        self.assertFalse(packet["custom_response_exact_token_observed"])

    def test_cdp_response_observer_reports_completion_without_exact_token(self) -> None:
        cdp_packets = [
            {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 1,
                            "responseSurfaceCandidateCount": 2,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 3,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ]
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_POLL_SECONDS",
                0.0,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=cdp_packets,
            ),
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-completed",
                request_id="native-submit-completed",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["assistant_turn_activity_observed"])
        self.assertTrue(packet["assistant_turn_started_observed"])
        self.assertTrue(packet["assistant_turn_completed_observed"])
        self.assertTrue(packet["assistant_turn_activity_ended_observed"])
        self.assertTrue(packet["assistant_turn_post_completion_scan_performed"])
        self.assertFalse(packet["assistant_turn_last_scan_active"])
        self.assertEqual(packet["assistant_turn_stop_generating_candidate_count"], 1)
        self.assertEqual(packet["response_surface_candidate_count"], 3)
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN",
        )
        self.assertFalse(packet["custom_response_exact_token_observed"])

    def test_cdp_response_observer_reports_completion_without_exact_even_with_prompt_echo(
        self,
    ) -> None:
        cdp_packets = [
            {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": True,
                            "assistantTurnStartedObserved": True,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 1,
                            "responseSurfaceCandidateCount": 2,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 1,
                            "promptSuffixEchoCandidateCount": 1,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
            {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 3,
                            "tokenLeafCandidateCount": 1,
                            "promptEchoCandidateCount": 1,
                            "promptSuffixEchoCandidateCount": 1,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            },
        ]
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_POLL_SECONDS",
                0.0,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=cdp_packets,
            ),
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-echo-completed",
                request_id="native-submit-echo-completed",
                timeout_seconds=0.1,
            )

        self.assertTrue(packet["assistant_turn_activity_observed"])
        self.assertTrue(packet["assistant_turn_completed_observed"])
        self.assertTrue(packet["assistant_turn_activity_ended_observed"])
        self.assertTrue(packet["assistant_turn_post_completion_scan_performed"])
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN",
        )
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertEqual(packet["custom_response_prompt_echo_candidate_count"], 1)

    def test_submit_custom_native_window_prompt_blocks_without_input_capable_window(self) -> None:
        with mock.patch(
            "wild_boar_proxy.native_window_probe.show_custom_native_window_packet",
            return_value={
                "status": "blocked",
                "machine_error_code": "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN",
                "custom_window_observed": True,
                "input_capable_ui_observed": False,
                "native_app_usable": False,
                "native_app_usability_blocked_reason_class": "input_capable_window_not_proven_for_pid",
            },
        ):
            packet = native_probe.submit_custom_native_window_prompt_packet(
                prompt="Planner: do it",
                request_id="native-submit-blocked",
            )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN")
        self.assertTrue(packet["native_window_observed"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertFalse(packet["prompt_submitted"])
        self.assertFalse(packet["native_agent_provider_call_directly_observed"])
        self.assertFalse(packet["custom_codex_response_text_read_proven"])
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN",
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])

    def test_submit_custom_native_window_prompt_passes_same_profile_candidate_pids_to_cdp(self) -> None:
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.show_custom_native_window_packet",
                return_value={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "custom_process_pid": 222,
                    "custom_window_candidate_pids": [222, 333],
                    "custom_window_observed": True,
                    "input_capable_ui_observed": True,
                    "native_app_usable": True,
                },
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_submit_prompt_to_app_page",
                return_value={
                    "status": "ok",
                    "machine_error_code": "OK",
                    "prompt_submitted": True,
                    "input_text_insert_succeeded": True,
                },
            ) as submitter,
        ):
            packet = native_probe.submit_custom_native_window_prompt_packet(
                prompt="Planner: do it",
                request_id="native-submit-ok",
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["prompt_submitted"])
        self.assertFalse(packet["native_agent_provider_call_directly_observed"])
        self.assertFalse(packet["custom_codex_response_text_read_proven"])
        self.assertFalse(packet["custom_response_exact_token_observed"])
        self.assertFalse(packet["custom_response_bound_to_request"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["native_codex_subagent_absence_proven"])
        self.assertEqual(
            packet["native_free_text_observer_machine_error_code"],
            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN",
        )
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        submitter.assert_called_once_with(
            222,
            "Planner: do it",
            request_id="native-submit-ok",
            expected_text="",
            port=int(native_probe.CODEX_REMOTE_DEBUGGING_PORT),
            allowed_owner_pids=[222, 333],
            observer_timeout_seconds=(
                native_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_WAIT_SECONDS
            ),
        )

    def test_submit_custom_native_window_prompt_uses_session_observer_when_cdp_exact_is_unbound(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            profile_root = base_dir / "wbp-custom-main"
            session_dir = profile_root / "sessions" / "2026" / "06" / "30"
            session_dir.mkdir(parents=True)
            request_id = "physical-natural-1782797606"
            expected_text = "WBP_PHYSICAL_NATURAL_OK_physical_natural_1782797606"
            prompt = f"DIP: ответь ровно {expected_text}"
            session_rows = [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": expected_text},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "id": "msg_wbp_external_route",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": expected_text}],
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": expected_text,
                    },
                },
            ]
            (session_dir / "thread.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in session_rows)
                + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.show_custom_native_window_packet",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "custom_process_pid": 222,
                        "custom_window_candidate_pids": [222],
                        "custom_window_observed": True,
                        "input_capable_ui_observed": True,
                        "native_app_usable": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_submit_prompt_to_app_page",
                    return_value={
                        "schema_version": 1,
                        "packet_kind": "custom_codex_native_prompt_submit",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "request_id": request_id,
                        "native_window_observed": True,
                        "input_capable_ui_observed": True,
                        "input_text_insert_succeeded": True,
                        "prompt_submitted": True,
                        "custom_codex_response_text_read_proven": True,
                        "custom_response_exact_token_observed": True,
                        "custom_response_bound_to_request": False,
                        "native_codex_subagent_used_as_dip": False,
                        "native_codex_subagent_absence_proven": True,
                        "native_free_text_observer_source": (
                            "bounded_cdp_response_token_scan"
                        ),
                        "native_free_text_observer_machine_error_code": (
                            "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                        ),
                        "raw_prompt_recorded": False,
                        "prompt_text_recorded": False,
                    },
                ),
            ):
                packet = native_probe.submit_custom_native_window_prompt_packet(
                    prompt=prompt,
                    request_id=request_id,
                    expected_text=expected_text,
                    persistent_profile_base_dir=base_dir,
                    observer_timeout_seconds=5.0,
                )

        self.assertTrue(packet["custom_response_exact_token_observed"])
        self.assertTrue(packet["custom_response_bound_to_request"])
        self.assertEqual(
            packet["native_free_text_observer_source"],
            "custom_session_jsonl_external_route",
        )
        session_packet = packet["custom_session_external_route_observer_packet"]
        self.assertEqual(session_packet["status"], "ok")
        self.assertTrue(session_packet["custom_session_prompt_digest_bound"])
        self.assertTrue(session_packet["custom_session_external_route_message_observed"])
        self.assertTrue(session_packet["custom_session_task_complete_observed"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])

    def test_native_ui_observer_proof_command_writes_file_backed_native_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "req-1",
                    "prompt_sha256": "abc",
                    "prompt_length": 8,
                    "native_window_observed": True,
                    "input_capable_ui_observed": True,
                    "native_app_usable": True,
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": "OK",
                    "input_text_insert_succeeded": True,
                    "custom_codex_response_text_read_proven": True,
                    "custom_response_exact_token_observed": True,
                    "custom_response_bound_to_request": True,
                    "native_codex_subagent_used_as_dip": False,
                    "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                    "native_free_text_observer_machine_error_code": "OK",
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ) as submitter:
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-1",
                    expected_text="WBP_NATIVE_req-1",
                    proof_dir=str(proof_dir),
                    persistent_profile_id="wbp-custom-main",
                    persistent_profile_base_dir=str(root / "profiles"),
                    observer_timeout_seconds=45.0,
                )

            submitter.assert_called_once()
            self.assertEqual(
                submitter.call_args.kwargs["observer_timeout_seconds"],
                45.0,
            )
            self.assertEqual(packet["packet_kind"], "custom_codex_native_prompt_submit")
            self.assertTrue(packet["native_ui_observer_packet_file_written"])
            self.assertFalse(packet["native_ui_observer_packet_file_path_recorded"])
            self.assertTrue(packet["native_ui_observer_packet_proven"])
            self.assertTrue(packet["native_ui_request_id_valid"])
            self.assertTrue(packet["native_ui_observer_packet_request_id_matches_input"])
            self.assertTrue(packet["native_ui_expected_text_contains_request_id"])
            self.assertTrue(packet["native_ui_strict_request_bound_observed"])
            self.assertTrue(packet["native_ui_exact_token_smoke_observed"])
            self.assertEqual(
                packet["native_ui_observer_proof_strength"],
                "strict_request_bound",
            )
            self.assertEqual(
                packet["native_ui_observer_proof_machine_error_code"],
                "OK",
            )
            self.assertEqual(packet["exit_code"], 0)
            self.assertFalse(packet["product_ready"])
            written = proof_dir / "native-ui-observer.packet.json"
            self.assertTrue(written.exists())
            persisted = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(persisted["request_id"], "req-1")

    def test_native_ui_observer_proof_command_does_not_greenwash_exact_token_smoke_without_request_binding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "req-smoke",
                    "prompt_sha256": "abc",
                    "prompt_length": 8,
                    "native_window_observed": True,
                    "input_capable_ui_observed": True,
                    "native_app_usable": True,
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": (
                        "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_PROVEN"
                    ),
                    "input_text_insert_succeeded": True,
                    "custom_codex_response_text_read_proven": True,
                    "custom_response_exact_token_observed": True,
                    "custom_response_bound_to_request": False,
                    "native_codex_subagent_used_as_dip": False,
                    "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                    "native_free_text_observer_machine_error_code": (
                        "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                    ),
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-smoke",
                    expected_text="WBP_NATIVE_req-smoke",
                    proof_dir=str(proof_dir),
                )

            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertTrue(packet["native_ui_request_id_valid"])
            self.assertTrue(packet["native_ui_observer_packet_request_id_matches_input"])
            self.assertTrue(packet["native_ui_expected_text_contains_request_id"])
            self.assertFalse(packet["native_ui_strict_request_bound_observed"])
            self.assertTrue(packet["native_ui_exact_token_smoke_observed"])
            self.assertEqual(
                packet["native_ui_observer_proof_strength"],
                "exact_token_smoke_only",
            )
            self.assertEqual(
                packet["native_ui_observer_proof_machine_error_code"],
                "CUSTOM_NATIVE_UI_OBSERVER_EXACT_TOKEN_SMOKE_ONLY",
            )
            self.assertFalse(packet["custom_response_bound_to_request"])
            self.assertEqual(
                packet["assistant_turn_machine_error_code"],
                "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_PROVEN",
            )

    def test_native_ui_observer_proof_command_fails_closed_when_expected_text_is_not_request_bound(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "req-unbound",
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": "OK",
                    "custom_codex_response_text_read_proven": True,
                    "custom_response_exact_token_observed": True,
                    "custom_response_bound_to_request": True,
                    "native_codex_subagent_used_as_dip": False,
                    "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                    "native_free_text_observer_machine_error_code": "OK",
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-unbound",
                    expected_text="WBP_NATIVE_VISIBLE_RESPONSE_ONLY",
                    proof_dir=str(proof_dir),
                )

            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertTrue(packet["native_ui_request_id_valid"])
            self.assertTrue(packet["native_ui_observer_packet_request_id_matches_input"])
            self.assertFalse(packet["native_ui_expected_text_contains_request_id"])
            self.assertFalse(packet["native_ui_strict_request_bound_observed"])
            self.assertTrue(packet["native_ui_exact_token_smoke_observed"])
            self.assertEqual(
                packet["native_ui_observer_proof_strength"],
                "exact_token_smoke_only",
            )
            self.assertEqual(
                packet["native_ui_observer_proof_machine_error_code"],
                "CUSTOM_NATIVE_UI_OBSERVER_EXPECTED_TEXT_NOT_REQUEST_BOUND",
            )

    def test_native_ui_observer_proof_command_fails_closed_when_request_id_is_invalid(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "bad request id",
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": "OK",
                    "custom_codex_response_text_read_proven": True,
                    "custom_response_exact_token_observed": True,
                    "custom_response_bound_to_request": True,
                    "native_codex_subagent_used_as_dip": False,
                    "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                    "native_free_text_observer_machine_error_code": "OK",
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="bad request id",
                    expected_text="WBP_NATIVE_bad request id",
                    proof_dir=str(proof_dir),
                )

            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertFalse(packet["native_ui_request_id_valid"])
            self.assertFalse(packet["native_ui_observer_packet_request_id_matches_input"])
            self.assertFalse(packet["native_ui_expected_text_contains_request_id"])
            self.assertFalse(packet["native_ui_strict_request_bound_observed"])
            self.assertTrue(packet["native_ui_exact_token_smoke_observed"])
            self.assertEqual(
                packet["native_ui_observer_proof_strength"],
                "exact_token_smoke_only",
            )
            self.assertEqual(
                packet["native_ui_observer_proof_machine_error_code"],
                "CUSTOM_NATIVE_UI_REQUEST_ID_INVALID",
            )

    def test_native_ui_observer_auto_launch_retries_after_missing_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            blocked_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "error",
                "machine_error_code": "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
                "request_id": "req-autolaunch",
                "native_window_observed": False,
                "input_capable_ui_observed": False,
                "prompt_submitted": False,
                "native_prompt_turn_accepted": False,
                "assistant_turn_machine_error_code": (
                    "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED"
                ),
                "native_free_text_observer_machine_error_code": (
                    "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                ),
                "custom_response_exact_token_observed": False,
                "custom_response_bound_to_request": False,
                "native_codex_subagent_used_as_dip": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            proven_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "ok",
                "machine_error_code": "OK",
                "request_id": "req-autolaunch",
                "native_window_observed": True,
                "input_capable_ui_observed": True,
                "native_app_usable": True,
                "prompt_submitted": True,
                "native_prompt_turn_accepted": True,
                "assistant_turn_machine_error_code": "OK",
                "custom_response_exact_token_observed": True,
                "custom_response_bound_to_request": True,
                "native_codex_subagent_used_as_dip": False,
                "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                "native_free_text_observer_machine_error_code": "OK",
                "custom_codex_ui_visibility_proven": False,
                "product_ready": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            launch_packet = {
                "status": "ok",
                "machine_error_code": "OK",
                "process_started": True,
                "running_status": True,
                "native_app_usable": True,
                "reused_existing_window": False,
                "existing_custom_window_reused": False,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "submit_custom_native_window_prompt_packet",
                    side_effect=[blocked_packet, proven_packet],
                ) as submitter,
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "launch_custom_native_app_packet",
                    return_value=launch_packet,
                ) as launcher,
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-autolaunch",
                    expected_text="WBP_NATIVE_req-autolaunch",
                    proof_dir=str(proof_dir),
                    persistent_profile_base_dir=str(root / "profiles"),
                    auto_launch_custom_codex=True,
                    auto_launch_endpoint="http://127.0.0.1:8318/v1",
                    auto_launch_model="gpt-5.3-codex",
                    auto_launch_owner_authorization_phrase=(
                        OWNER_STANDING_AUTHORIZATION_PHRASE
                    ),
                    auto_launch_repo_root=str(ROOT),
                    auto_launch_stable_runtime_generated_config_file=str(
                        root / "managed" / "stable-runtime-config.generated.yaml"
                    ),
                )

            self.assertEqual(submitter.call_count, 2)
            launcher.assert_called_once()
            self.assertEqual(
                launcher.call_args.kwargs["stable_runtime_generated_config_file"],
                root / "managed" / "stable-runtime-config.generated.yaml",
            )
            self.assertTrue(packet["native_ui_observer_retry_after_auto_launch"])
            self.assertTrue(packet["native_auto_launch_attempted"])
            self.assertTrue(packet["native_auto_launch_packet_file_written"])
            self.assertFalse(packet["native_auto_launch_local_token_value_recorded"])
            self.assertTrue(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 0)
            self.assertTrue((proof_dir / NATIVE_UI_AUTO_LAUNCH_PACKET_FILE_NAME).exists())
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(OWNER_STANDING_AUTHORIZATION_PHRASE, serialized)

    def test_native_ui_observer_auto_launch_retries_after_existing_window_not_input_capable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            blocked_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "blocked",
                "machine_error_code": "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN",
                "request_id": "req-window-not-input",
                "native_window_observed": True,
                "input_capable_ui_observed": False,
                "prompt_submitted": False,
                "native_prompt_turn_accepted": False,
                "assistant_turn_machine_error_code": (
                    "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED"
                ),
                "native_free_text_observer_machine_error_code": (
                    "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                ),
                "custom_response_exact_token_observed": False,
                "custom_response_bound_to_request": False,
                "native_codex_subagent_used_as_dip": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            proven_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "ok",
                "machine_error_code": "OK",
                "request_id": "req-window-not-input",
                "native_window_observed": True,
                "input_capable_ui_observed": True,
                "native_app_usable": True,
                "prompt_submitted": True,
                "native_prompt_turn_accepted": True,
                "assistant_turn_machine_error_code": "OK",
                "custom_response_exact_token_observed": True,
                "custom_response_bound_to_request": True,
                "native_codex_subagent_used_as_dip": False,
                "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                "native_free_text_observer_machine_error_code": "OK",
                "custom_codex_ui_visibility_proven": False,
                "product_ready": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            launch_packet = {
                "status": "ok",
                "machine_error_code": "OK",
                "process_started": True,
                "running_status": True,
                "native_app_usable": True,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "submit_custom_native_window_prompt_packet",
                    side_effect=[blocked_packet, proven_packet],
                ) as submitter,
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "launch_custom_native_app_packet",
                    return_value=launch_packet,
                ) as launcher,
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-window-not-input",
                    expected_text="WBP_NATIVE_req-window-not-input",
                    proof_dir=str(proof_dir),
                    auto_launch_custom_codex=True,
                    auto_launch_owner_authorization_phrase=(
                        OWNER_STANDING_AUTHORIZATION_PHRASE
                    ),
                    auto_launch_repo_root=str(ROOT),
                )

            self.assertEqual(submitter.call_count, 2)
            launcher.assert_called_once()
            self.assertTrue(packet["native_ui_observer_retry_after_auto_launch"])
            self.assertTrue(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 0)

    def test_native_ui_observer_auto_launch_retries_after_window_usability_pending(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            blocked_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "error",
                "machine_error_code": "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
                "request_id": "req-usability-pending",
                "native_window_observed": False,
                "input_capable_ui_observed": False,
                "prompt_submitted": False,
                "native_prompt_turn_accepted": False,
                "assistant_turn_machine_error_code": (
                    "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED"
                ),
                "native_free_text_observer_machine_error_code": (
                    "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                ),
                "custom_response_exact_token_observed": False,
                "custom_response_bound_to_request": False,
                "native_codex_subagent_used_as_dip": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            proven_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "ok",
                "machine_error_code": "OK",
                "request_id": "req-usability-pending",
                "native_window_observed": True,
                "input_capable_ui_observed": True,
                "native_app_usable": True,
                "prompt_submitted": True,
                "native_prompt_turn_accepted": True,
                "assistant_turn_machine_error_code": "OK",
                "custom_response_exact_token_observed": True,
                "custom_response_bound_to_request": True,
                "native_codex_subagent_used_as_dip": False,
                "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                "native_free_text_observer_machine_error_code": "OK",
                "custom_codex_ui_visibility_proven": False,
                "product_ready": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            launch_packet = {
                "status": "blocked",
                "machine_error_code": "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN",
                "process_started": True,
                "native_window_observed": True,
                "running_status": False,
                "native_app_usable": False,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "submit_custom_native_window_prompt_packet",
                    side_effect=[blocked_packet, proven_packet],
                ) as submitter,
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "launch_custom_native_app_packet",
                    return_value=launch_packet,
                ),
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-usability-pending",
                    expected_text="WBP_NATIVE_req-usability-pending",
                    proof_dir=str(proof_dir),
                    auto_launch_custom_codex=True,
                    auto_launch_owner_authorization_phrase=(
                        OWNER_STANDING_AUTHORIZATION_PHRASE
                    ),
                    auto_launch_repo_root=str(ROOT),
                )

            self.assertEqual(submitter.call_count, 2)
            self.assertTrue(packet["native_ui_observer_retry_after_auto_launch"])
            self.assertTrue(packet["native_auto_launch_attempted"])
            self.assertFalse(packet["native_auto_launch_native_app_usable"])
            self.assertTrue(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 0)

    def test_native_ui_observer_auto_launch_retries_after_window_not_proven_but_running(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            blocked_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "error",
                "machine_error_code": "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
                "request_id": "req-window-not-proven",
                "native_window_observed": False,
                "input_capable_ui_observed": False,
                "prompt_submitted": False,
                "native_prompt_turn_accepted": False,
                "assistant_turn_machine_error_code": (
                    "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED"
                ),
                "native_free_text_observer_machine_error_code": (
                    "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                ),
                "custom_response_exact_token_observed": False,
                "custom_response_bound_to_request": False,
                "native_codex_subagent_used_as_dip": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            proven_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "ok",
                "machine_error_code": "OK",
                "request_id": "req-window-not-proven",
                "native_window_observed": True,
                "input_capable_ui_observed": True,
                "native_app_usable": True,
                "prompt_submitted": True,
                "native_prompt_turn_accepted": True,
                "assistant_turn_machine_error_code": "OK",
                "custom_response_exact_token_observed": True,
                "custom_response_bound_to_request": True,
                "native_codex_subagent_used_as_dip": False,
                "native_free_text_observer_source": "bounded_cdp_response_token_scan",
                "native_free_text_observer_machine_error_code": "OK",
                "custom_codex_ui_visibility_proven": False,
                "product_ready": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            launch_packet = {
                "status": "blocked",
                "machine_error_code": "CUSTOM_NATIVE_WINDOW_NOT_PROVEN",
                "process_started": True,
                "running_status": True,
                "native_app_usable": False,
                "cleanup_deferred_while_running": True,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "submit_custom_native_window_prompt_packet",
                    side_effect=[blocked_packet, proven_packet],
                ) as submitter,
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "launch_custom_native_app_packet",
                    return_value=launch_packet,
                ),
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-window-not-proven",
                    expected_text="WBP_NATIVE_req-window-not-proven",
                    proof_dir=str(proof_dir),
                    auto_launch_custom_codex=True,
                    auto_launch_owner_authorization_phrase=(
                        OWNER_STANDING_AUTHORIZATION_PHRASE
                    ),
                    auto_launch_repo_root=str(ROOT),
                )

            self.assertEqual(submitter.call_count, 2)
            self.assertTrue(packet["native_ui_observer_retry_after_auto_launch"])
            self.assertTrue(packet["native_auto_launch_attempted"])
            self.assertTrue(packet["native_auto_launch_running_status"])
            self.assertFalse(packet["native_auto_launch_native_app_usable"])
            self.assertTrue(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 0)

    def test_native_ui_observer_auto_launch_does_not_greenwash_launch_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            blocked_packet = {
                "schema_version": 1,
                "packet_kind": "custom_codex_native_prompt_submit",
                "status": "error",
                "machine_error_code": "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
                "request_id": "req-launch-only",
                "native_window_observed": False,
                "input_capable_ui_observed": False,
                "prompt_submitted": False,
                "native_prompt_turn_accepted": False,
                "assistant_turn_machine_error_code": (
                    "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED"
                ),
                "native_free_text_observer_machine_error_code": (
                    "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                ),
                "custom_response_exact_token_observed": False,
                "custom_response_bound_to_request": False,
                "native_codex_subagent_used_as_dip": False,
                "fallback_used": False,
                "local_imitation_used": False,
            }
            launch_packet = {
                "status": "blocked",
                "machine_error_code": "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN",
                "process_started": True,
                "running_status": False,
                "native_app_usable": False,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "submit_custom_native_window_prompt_packet",
                    return_value=blocked_packet,
                ) as submitter,
                mock.patch(
                    "wild_boar_proxy.custom_codex_native_ui_observer_proof."
                    "launch_custom_native_app_packet",
                    return_value=launch_packet,
                ),
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-launch-only",
                    expected_text="WBP_NATIVE_req-launch-only",
                    proof_dir=str(proof_dir),
                    auto_launch_custom_codex=True,
                    auto_launch_owner_authorization_phrase=(
                        OWNER_STANDING_AUTHORIZATION_PHRASE
                    ),
                    auto_launch_repo_root=str(ROOT),
                )

            submitter.assert_called_once()
            self.assertTrue(packet["native_auto_launch_attempted"])
            self.assertFalse(packet["native_auto_launch_native_app_usable"])
            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertTrue((proof_dir / NATIVE_UI_AUTO_LAUNCH_PACKET_FILE_NAME).exists())

    def test_native_ui_observer_proof_command_does_not_greenwash_prompt_submit_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "req-echo",
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": (
                        "CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY"
                    ),
                    "custom_response_exact_token_observed": False,
                    "custom_response_bound_to_request": False,
                    "native_codex_subagent_used_as_dip": False,
                    "native_free_text_observer_machine_error_code": (
                        "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                    ),
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-echo",
                    expected_text="WBP_NATIVE_req-echo",
                    proof_dir=str(proof_dir),
                )

            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            persisted = json.loads(
                (proof_dir / "native-ui-observer.packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(persisted["native_ui_observer_packet_proven"])
            self.assertEqual(persisted["exit_code"], 1)

    def test_native_ui_observer_proof_command_does_not_greenwash_candidate_map_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SimpleNamespace(managed_dir=root / "managed")
            proof_dir = root / "proof"
            with mock.patch(
                "wild_boar_proxy.custom_codex_native_ui_observer_proof.submit_custom_native_window_prompt_packet",
                return_value={
                    "schema_version": 1,
                    "packet_kind": "custom_codex_native_prompt_submit",
                    "status": "ok",
                    "machine_error_code": "OK",
                    "request_id": "req-map-only",
                    "prompt_submitted": True,
                    "native_prompt_turn_accepted": True,
                    "assistant_turn_machine_error_code": (
                        "CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN"
                    ),
                    "native_free_text_observer_machine_error_code": (
                        "CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN"
                    ),
                    "custom_response_exact_token_observed": False,
                    "custom_response_bound_to_request": False,
                    "custom_response_candidate_map_available": True,
                    "custom_response_candidate_map_candidate_count": 2,
                    "custom_response_candidate_map": [
                        {
                            "candidate_kind": "prompt_echo",
                            "text_sha256": "a" * 64,
                            "contains_expected_text": True,
                        },
                        {
                            "candidate_kind": "response_surface",
                            "text_sha256": "b" * 64,
                            "contains_expected_text": False,
                        },
                    ],
                    "native_codex_subagent_used_as_dip": False,
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                },
            ):
                packet = run_native_ui_observer_proof_command(
                    paths=paths,
                    prompt_text="prompt",
                    request_id="req-map-only",
                    expected_text="WBP_NATIVE_req-map-only",
                    proof_dir=str(proof_dir),
                )

            self.assertFalse(packet["native_ui_observer_packet_proven"])
            self.assertEqual(packet["exit_code"], 1)
            self.assertFalse(packet["custom_codex_ui_visibility_proven"])
            self.assertFalse(packet["product_ready"])
            persisted = json.loads(
                (proof_dir / "native-ui-observer.packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(persisted["native_ui_observer_packet_proven"])
            self.assertEqual(persisted["exit_code"], 1)
            self.assertTrue(persisted["custom_response_candidate_map_available"])

    def test_cdp_response_observer_allows_explicit_bounded_wait_above_default(self) -> None:
        scan_count: list[int] = []

        def fake_cdp_command(_ws_url: str, _message: dict[str, Any], **_kwargs: object) -> dict[str, Any]:
            scan_count.append(1)
            return {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 0,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            }

        monotonic_values = iter([0.0, 0.0, 45.0, 46.0])
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.time.monotonic",
                side_effect=lambda: next(monotonic_values),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_POLL_SECONDS",
                0.0,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe.time.sleep",
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=fake_cdp_command,
            ),
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-long-wait",
                request_id="native-submit-long-wait",
                timeout_seconds=45.0,
            )

        self.assertEqual(len(scan_count), 2)
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED",
        )

    def test_cdp_response_observer_allows_slow_dip_ui_turn_budget(self) -> None:
        scan_count: list[int] = []

        def fake_cdp_command(_ws_url: str, _message: dict[str, Any], **_kwargs: object) -> dict[str, Any]:
            scan_count.append(1)
            return {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 0,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            }

        self.assertGreaterEqual(
            native_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_WAIT_SECONDS,
            240.0,
        )
        self.assertGreaterEqual(
            native_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_MAX_WAIT_SECONDS,
            240.0,
        )
        monotonic_values = iter([0.0, 0.0, 120.0, 239.9, 240.1])
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.time.monotonic",
                side_effect=lambda: next(monotonic_values),
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe.CUSTOM_NATIVE_RESPONSE_OBSERVER_POLL_SECONDS",
                0.0,
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe.time.sleep",
            ),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=fake_cdp_command,
            ),
        ):
            packet = native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-slow-dip-turn",
                request_id="native-submit-slow-dip-turn",
                timeout_seconds=999.0,
            )

        self.assertEqual(len(scan_count), 3)
        self.assertEqual(
            packet["assistant_turn_machine_error_code"],
            "CUSTOM_NATIVE_ASSISTANT_TURN_NOT_OBSERVED",
        )

    def test_cdp_response_observer_scopes_blocker_markers_to_current_turn(self) -> None:
        expressions: list[str] = []

        def fake_cdp_command(_ws_url: str, message: dict[str, Any], **_kwargs: object) -> dict[str, Any]:
            params = message.get("params")
            if isinstance(params, dict):
                expressions.append(str(params.get("expression") or ""))
            return {
                "id": 3700,
                "result": {
                    "result": {
                        "value": {
                            "responseObserverScanPerformed": True,
                            "responseTextReadWithoutStoring": True,
                            "assistantTurnProbeScanPerformed": True,
                            "assistantTurnActivityObserved": False,
                            "assistantTurnStartedObserved": False,
                            "assistantTurnCompletedObserved": False,
                            "assistantTurnFailedObserved": False,
                            "authOrBackendBlockerObserved": False,
                            "modelOrRuntimeBlockerObserved": False,
                            "progressCandidateCount": 0,
                            "stopGeneratingCandidateCount": 0,
                            "responseSurfaceCandidateCount": 0,
                            "tokenLeafCandidateCount": 0,
                            "promptEchoCandidateCount": 0,
                            "promptSuffixEchoCandidateCount": 0,
                            "exactTokenCandidateCount": 0,
                            "responseLikeCandidateCount": 0,
                            "subagentMarkerCandidateCount": 0,
                            "customResponseExactTokenObserved": False,
                            "customResponseBoundToRequest": False,
                            "nativeCodexSubagentUsedAsDip": False,
                            "nativeCodexSubagentAbsenceProven": False,
                            "textValueCaptured": False,
                        }
                    }
                },
            }

        monotonic_values = iter([0.0, 0.0, 0.2])
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe.time.monotonic",
                side_effect=lambda: next(monotonic_values),
            ),
            mock.patch("wild_boar_proxy.native_window_probe.time.sleep"),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=fake_cdp_command,
            ),
        ):
            native_probe._cdp_observe_custom_response_token(
                "ws://127.0.0.1:9223/devtools/page/1",
                expected_text="WBP_NATIVE_RESPONSE_OK_native-submit-scoped-blocker",
                request_id="native-submit-scoped-blocker",
                timeout_seconds=0.1,
            )

        self.assertEqual(len(expressions), 1)
        self.assertNotIn("document.body && document.body.innerText", expressions[0])
        self.assertIn("requestPromptBottom", expressions[0])
        self.assertIn("currentTurnRegion", expressions[0])
        self.assertIn("unknown provider for model", expressions[0])

    def test_cdp_input_capable_accepts_later_app_page_target_with_visible_surface(self) -> None:
        response = mock.MagicMock()
        response.__enter__ = mock.Mock(return_value=response)
        response.__exit__ = mock.Mock(return_value=None)
        response.read.return_value = json.dumps(
            [
                {
                    "type": "page",
                    "url": "app://-/index.html?stale",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/1",
                },
                {
                    "type": "page",
                    "url": "app://-/index.html",
                    "webSocketDebuggerUrl": "ws://127.0.0.1:9223/devtools/page/2",
                },
            ]
        ).encode("utf-8")
        startup_loader_packet = {
            "id": 1,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html?stale",
                        "title": "Codex",
                        "inputCandidateCount": 0,
                        "visibleInputCandidateCount": 0,
                        "textValueCaptured": False,
                        "startupLoaderCount": 1,
                    }
                }
            },
        }
        input_surface_packet = {
            "id": 1,
            "result": {
                "result": {
                    "value": {
                        "readyState": "complete",
                        "url": "app://-/index.html",
                        "title": "Codex",
                        "inputCandidateCount": 1,
                        "visibleInputCandidateCount": 1,
                        "textValueCaptured": False,
                        "startupLoaderCount": 0,
                    }
                }
            },
        }
        with (
            mock.patch(
                "wild_boar_proxy.native_window_probe._devtools_port_owned_by_pid",
                return_value=(True, "222"),
            ),
            mock.patch("wild_boar_proxy.native_window_probe.urllib.request.urlopen", return_value=response),
            mock.patch(
                "wild_boar_proxy.native_window_probe._cdp_command",
                side_effect=[startup_loader_packet, input_surface_packet],
            ),
        ):
            input_capable, result = native_probe._cdp_input_capable(222, port=9223)

        self.assertTrue(input_capable)
        bounded = json.loads(result)
        self.assertEqual(bounded["cdp_target_url"], "app://-/index.html")
        self.assertEqual(bounded["cdp_page_target_count"], 2)
        self.assertEqual(bounded["cdp_visible_input_candidate_count"], 1)
        self.assertFalse(bounded["browser_cdp_authority_widened"])

    def test_show_custom_native_window_focuses_only_wbp_profile_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            profile_root = profile_base / "wbp-custom-main"
            native_fs.remote_debugging_port_file(profile_root).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            native_fs.remote_debugging_port_file(profile_root).write_text(
                "49231\n",
                encoding="utf-8",
            )
            process_inventory = {
                "root_app_pids": [111, 222],
                "custom_process_lines": [
                    f"222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir={user_data_dir}"
                ],
            }
            before = {
                "window_observed": True,
                "observed_pid": 222,
                "window_visible": True,
                "window_frontmost": False,
                "window_bounds": {"x": 793, "y": 0, "width": 1280, "height": 783},
            }
            after = {
                "window_observed": True,
                "observed_pid": 222,
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[before, after],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 222,
                        "window_focus_bounds": after["window_bounds"],
                    },
                ) as focus,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ) as usability,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_voice_icon_observation",
                    return_value={
                        "packet_kind": "custom_codex_native_voice_icon_observation",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "native_voice_icon_observed": True,
                        "native_voice_shortcut_available": False,
                        "native_voice_shortcut_tested": False,
                        "voice_blocked_reason_code": "",
                        "voice_shortcut_blocked_reason_code": "VOICE_SHORTCUT_NOT_TESTED_NO_UI_MUTATION",
                        "microphone_permission_check_required": True,
                        "does_not_patch_codex_ui": True,
                        "voice_is_not_locally_imitated": True,
                    },
                ) as voice_observation,
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["custom_process_pid"], 222)
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(packet["input_capable_ui_observed"])
        self.assertTrue(packet["native_voice_icon_observed"])
        self.assertTrue(packet["microphone_permission_check_required"])
        self.assertEqual(packet["cdp_port"], 49231)
        self.assertEqual(
            packet["cdp_port_source"],
            "persistent_profile_remote_debugging_port",
        )
        self.assertEqual(
            packet["voice_shortcut_blocked_reason_code"],
            "VOICE_SHORTCUT_NOT_TESTED_NO_UI_MUTATION",
        )
        self.assertTrue(packet["does_not_patch_codex_ui"])
        self.assertTrue(packet["voice_is_not_locally_imitated"])
        self.assertEqual(packet["custom_window_bounds"]["x"], 120)
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        focus.assert_called_once_with(222)
        usability.assert_called_once_with(after, cdp_port=49231)
        voice_observation.assert_called_once_with(
            222,
            port=49231,
            allowed_owner_pids=[222],
        )

    def test_show_custom_native_window_can_use_focus_visibility_fallback_when_ax_window_count_stays_zero(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            profile_root = profile_base / "wbp-custom-main"
            native_fs.remote_debugging_port_file(profile_root).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            native_fs.remote_debugging_port_file(profile_root).write_text(
                "49231\n",
                encoding="utf-8",
            )
            process_inventory = {
                "root_app_pids": [222],
                "custom_process_lines": [
                    f"222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir={user_data_dir}"
                ],
            }
            before = {
                "window_observed": False,
                "observed_pid": 333,
                "window_visible": False,
                "window_frontmost": False,
                "window_bounds": {},
                "blocked_reason_class": "pid_visible_but_accessible_window_absent",
                "window_query_method": "AX/System Events process window count",
            }
            after = {
                "window_observed": False,
                "observed_pid": 333,
                "window_visible": False,
                "window_frontmost": False,
                "window_bounds": {},
                "blocked_reason_class": "pid_visible_but_accessible_window_absent",
                "window_query_method": "AX/System Events process window count",
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[before, after],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": False,
                        "window_focus_query": "Codex\ttrue\ttrue\t0",
                        "window_focus_query_rc": 0,
                        "window_focus_query_error_class": "",
                        "window_focus_stderr_bounded": "",
                        "window_focus_observed_pid": 222,
                        "window_focus_visible": True,
                        "window_focus_frontmost": True,
                        "window_focus_window_count": 0,
                        "window_focus_bounds": {},
                    },
                ) as focus,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                        "native_app_usability_source": "cdp_renderer_input_capable_ui",
                    },
                ) as usability,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_voice_icon_observation",
                    return_value={
                        "packet_kind": "custom_codex_native_voice_icon_observation",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "native_voice_icon_observed": True,
                        "native_voice_shortcut_available": False,
                        "native_voice_shortcut_tested": False,
                        "voice_blocked_reason_code": "",
                        "voice_shortcut_blocked_reason_code": "",
                        "microphone_permission_check_required": False,
                        "does_not_patch_codex_ui": True,
                        "voice_is_not_locally_imitated": True,
                    },
                ),
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["custom_window_observed"])
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertTrue(packet["native_app_usable"])
        self.assertFalse(packet["window_focus_action_succeeded"])
        self.assertTrue(
            packet["window_observation_after_focus"]["window_focus_visibility_fallback_used"]
        )
        focus.assert_called_once_with(222)
        self.assertTrue(
            usability.call_args.args[0]["window_focus_visibility_fallback_used"]
        )

    def test_show_custom_native_window_can_use_fresh_window_lifecycle_scope_when_ax_reports_zero_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            profile_root = profile_base / "wbp-custom-main"
            native_fs.remote_debugging_port_file(profile_root).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            native_fs.remote_debugging_port_file(profile_root).write_text(
                "49231\n",
                encoding="utf-8",
            )
            scope_path = profile_root / "electron-user-data" / "sentry" / "scope_v3.json"
            scope_path.parent.mkdir(parents=True, exist_ok=True)
            scope_path.write_text(
                json.dumps(
                    {
                        "scope": {
                            "breadcrumbs": [
                                {"message": "app.browser-window-created"},
                                {"message": "window.show"},
                                {"message": "app.browser-window-focus"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            process_inventory = {
                "root_app_pids": [222],
                "custom_process_lines": [
                    f"222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir={user_data_dir}"
                ],
            }
            completed = subprocess.CompletedProcess(
                args=["osascript"],
                returncode=0,
                stdout="Codex\ttrue\ttrue\tfalse\t0\n",
                stderr="",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.subprocess.run",
                    return_value=completed,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cg_window_presence",
                    return_value=(False, "cg_query_unavailable_pyobjc_framework_quartz_not_installed"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 222,
                        "window_focus_bounds": {},
                    },
                ) as focus,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ) as usability,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_voice_icon_observation",
                    return_value={
                        "packet_kind": "custom_codex_native_voice_icon_observation",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "native_voice_icon_observed": True,
                        "native_voice_shortcut_available": False,
                        "native_voice_shortcut_tested": False,
                        "voice_blocked_reason_code": "",
                        "voice_shortcut_blocked_reason_code": "VOICE_SHORTCUT_NOT_TESTED_NO_UI_MUTATION",
                        "microphone_permission_check_required": False,
                        "does_not_patch_codex_ui": True,
                        "voice_is_not_locally_imitated": True,
                    },
                ),
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["custom_window_observed"])
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(
            packet["window_observation_before_focus"]["window_lifecycle_scope_fallback_used"]
        )
        self.assertTrue(
            packet["window_observation_after_focus"]["window_lifecycle_scope_fallback_used"]
        )
        focus.assert_called_once_with(222)
        self.assertTrue(
            usability.call_args.args[0]["window_lifecycle_scope_fallback_used"]
        )

    def test_show_custom_native_window_prefers_live_process_remote_debugging_port_over_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            profile_root = profile_base / "wbp-custom-main"
            native_fs.remote_debugging_port_file(profile_root).parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            native_fs.remote_debugging_port_file(profile_root).write_text(
                "49231\n",
                encoding="utf-8",
            )
            process_inventory = {
                "root_app_pids": [222],
                "custom_process_lines": [
                    (
                        "222 /Users/kirillponomarev/Applications/Codex WBP Clean.app/"
                        "Contents/MacOS/Codex --remote-debugging-port=9223 "
                        f"--user-data-dir={user_data_dir}"
                    )
                ],
            }
            before = {
                "window_observed": True,
                "observed_pid": 222,
                "window_visible": True,
                "window_frontmost": False,
                "window_bounds": {"x": 793, "y": 0, "width": 1280, "height": 783},
            }
            after = {
                "window_observed": True,
                "observed_pid": 222,
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[before, after],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 222,
                        "window_focus_bounds": after["window_bounds"],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ) as usability,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_voice_icon_observation",
                    return_value={
                        "packet_kind": "custom_codex_native_voice_icon_observation",
                        "status": "ok",
                        "machine_error_code": "OK",
                        "native_voice_icon_observed": True,
                        "native_voice_shortcut_available": False,
                        "native_voice_shortcut_tested": False,
                        "voice_blocked_reason_code": "",
                        "voice_shortcut_blocked_reason_code": "",
                        "microphone_permission_check_required": False,
                        "does_not_patch_codex_ui": True,
                        "voice_is_not_locally_imitated": True,
                    },
                ) as voice_observation,
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["cdp_port"], 9223)
        self.assertEqual(
            packet["cdp_port_source"],
            "custom_process_command_line_remote_debugging_port",
        )
        usability.assert_called_once_with(after, cdp_port=9223)
        voice_observation.assert_called_once_with(
            222,
            port=9223,
            allowed_owner_pids=[222],
        )

    def test_show_custom_native_window_accepts_helper_only_same_profile_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            process_inventory = {
                "root_app_pids": [111],
                "custom_process_lines": [
                    f"333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir={user_data_dir}"
                ],
                "default_process_lines": [
                    "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/me/Library/Application Support/Codex"
                ],
            }
            before = {
                "window_observed": True,
                "observed_pid": 333,
                "window_visible": True,
                "window_frontmost": False,
                "custom_window_candidate_pids": [333],
                "window_bounds": {"x": 793, "y": 0, "width": 1280, "height": 783},
            }
            after = {
                "window_observed": True,
                "observed_pid": 333,
                "window_visible": True,
                "window_frontmost": True,
                "custom_window_candidate_pids": [333],
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[before, after],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 333,
                        "window_focus_bounds": after["window_bounds"],
                    },
                ) as focus,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ),
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["custom_process_pid"], 333)
        self.assertEqual(packet["custom_root_process_pids"], [])
        self.assertEqual(packet["custom_profile_process_pids"], [333])
        self.assertEqual(packet["default_profile_process_pids"], [111])
        self.assertEqual(packet["custom_window_candidate_pids"], [333])
        self.assertFalse(packet["custom_root_process_observed"])
        self.assertEqual(packet["custom_window_focus_pid"], 333)
        self.assertTrue(packet["native_app_usable"])
        self.assertFalse(packet["original_codex_touched"])
        focus.assert_called_once_with(333)

    def test_identity_binding_accepts_helper_only_custom_profile_pid_not_default(self) -> None:
        launch_result = {
            "launcher_pid": 222,
            "startup_inventory": {
                "root_app_pids": [111],
                "custom_process_lines": [
                    "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data"
                ],
                "default_process_lines": [
                    "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/me/Library/Application Support/Codex"
                ],
            },
        }
        window_packet = {
            "window_observed": True,
            "observed_pid": 333,
            "window_query": "Codex Helper\ttrue\ttrue\tfalse\t1\t120,80\t1320,820",
        }
        layout = SimpleNamespace(launcher_path=Path("/tmp/wbp-launcher.sh"))

        packet = native_probe._build_identity_binding(
            window_packet,
            layout,
            launch_result,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["window_bound_to_custom_launch"])
        self.assertTrue(packet["window_distinguishable_from_original_codex"])
        self.assertEqual(packet["custom_root_process_pids"], [])
        self.assertEqual(packet["custom_profile_process_pids"], [333])
        self.assertEqual(packet["default_profile_process_pids"], [111])
        self.assertEqual(packet["custom_window_candidate_pids"], [333])

    def test_identity_binding_prefers_stability_inventory_for_same_profile_window_pid(
        self,
    ) -> None:
        launch_result = {
            "launcher_pid": 222,
            "startup_inventory": {
                "root_app_pids": [111],
                "custom_process_lines": [
                    "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                ],
                "default_process_lines": [
                    "999 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/me/Library/Application Support/Codex"
                ],
            },
            "stability_inventory": {
                "root_app_pids": [111],
                "custom_process_lines": [
                    "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                    "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                ],
                "default_process_lines": [
                    "999 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/Users/me/Library/Application Support/Codex"
                ],
            },
        }
        window_packet = {
            "window_observed": True,
            "observed_pid": 333,
            "window_query": "Codex Helper\ttrue\ttrue\tfalse\t1\t120,80\t1320,820",
        }
        layout = SimpleNamespace(launcher_path=Path("/tmp/wbp-launcher.sh"))

        packet = native_probe._build_identity_binding(
            window_packet,
            layout,
            launch_result,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["window_bound_to_custom_launch"])
        self.assertTrue(packet["window_distinguishable_from_original_codex"])
        self.assertEqual(packet["custom_root_process_pids"], [111])
        self.assertEqual(packet["custom_profile_process_pids"], [111, 333])
        self.assertEqual(packet["default_profile_process_pids"], [999])
        self.assertEqual(packet["custom_window_candidate_pids"], [111, 333])

    def test_show_custom_native_window_does_not_promote_visible_window_to_usable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
            )
            process_inventory = {
                "root_app_pids": [222],
                "custom_process_lines": [
                    f"222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir={user_data_dir}"
                ],
            }
            after = {
                "window_observed": True,
                "observed_pid": 222,
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=process_inventory,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value=after,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 222,
                        "window_focus_bounds": after["window_bounds"],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "input_capable_ui_observed": False,
                        "blocked_reason_class": "input_capable_ui_not_proven_for_pid_window_present",
                    },
                ),
            ):
                packet = native_probe.show_custom_native_window_packet(
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN")
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertEqual(packet["next_action"], "stop_and_diagnose_window_usability")

    def test_live_custom_native_launch_accepts_pid_bound_window_proof_without_usability_greenwash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_NOT_PROVEN")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertTrue(packet["native_window_observed"])
        self.assertFalse(packet["native_app_usable"])
        self.assertTrue(packet["keychain_preflight_attempted"])
        self.assertEqual(packet["keychain_preflight_status"], "ok")
        self.assertEqual(packet["keychain_preflight_reason_code"], "OK")
        self.assertTrue(packet["isolated_default_keychain_verified"])
        self.assertTrue(packet["isolated_search_list_verified"])
        self.assertEqual(packet["prompt_avoidance_claim_scope"], "keychain_not_found_prompt_only")
        self.assertFalse(packet["real_user_keychain_modified"])
        self.assertFalse(packet["keychain_item_read"])
        self.assertFalse(packet["keychain_reset_performed"])

    def test_live_custom_native_launch_does_not_treat_runtime_ready_as_window_usability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            launcher_stdout = temp_root / "launcher.stdout.log"
            launcher_stdout.write_text(
                "\n".join(
                    [
                        "[electron-message-handler] Handled 'ready' message, sent ide-context-updated",
                        "[AppServerConnection] response_routed method=model/list",
                        "[browser-session-registry] browser_use_iab_backend_startup_ready",
                    ]
                ),
                encoding="utf-8",
            )
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=launcher_stdout,
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                        "launcher_stdout_path": str(launcher_stdout),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_NOT_PROVEN")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertTrue(packet["runtime_ready_observed"])
        self.assertFalse(packet["custom_window_visible"])
        self.assertEqual(packet["native_app_usability_source"], "not_proven")
        self.assertEqual(
            packet["native_app_usability_blocked_reason_class"],
            "input_capable_window_not_proven_for_pid",
        )

    def test_live_custom_native_launch_does_not_accept_visible_window_without_input_capable_ui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            launcher_stdout = temp_root / "launcher.stdout.log"
            launcher_stdout.write_text(
                "\n".join(
                    [
                        "[electron-message-handler] Handled 'ready' message, sent ide-context-updated",
                        "[AppServerConnection] response_routed method=model/list",
                        "[browser-session-registry] browser_use_iab_backend_startup_ready",
                    ]
                ),
                encoding="utf-8",
            )
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=launcher_stdout,
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                        "launcher_stdout_path": str(launcher_stdout),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 222,
                        "blocked_reason_class": "",
                        "window_visible": True,
                        "window_frontmost": True,
                        "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertTrue(packet["runtime_ready_observed"])
        self.assertTrue(packet["running_status"])
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertEqual(packet["native_app_usability_source"], "not_proven")
        self.assertEqual(packet["next_action"], "stop_and_diagnose_custom_window_usability")
        self.assertEqual(packet["custom_window_bounds"]["width"], 1320)

    def test_live_custom_native_launch_rechecks_delayed_cdp_input_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            launcher_stdout = temp_root / "launcher.stdout.log"
            launcher_stdout.write_text(
                "\n".join(
                    [
                        "[electron-message-handler] Handled 'ready' message, sent ide-context-updated",
                        "[AppServerConnection] response_routed method=model/list",
                        "[browser-session-registry] browser_use_iab_backend_startup_ready",
                    ]
                ),
                encoding="utf-8",
            )
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=launcher_stdout,
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            window_packet = {
                "window_observed": True,
                "observed_pid": 222,
                "blocked_reason_class": "",
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                        "launcher_stdout_path": str(launcher_stdout),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value={
                        "root_app_pids": [222],
                        "custom_process_lines": [
                            "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                        ],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value=window_packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    side_effect=[
                        {
                            "native_window_usable": False,
                            "input_capable_ui_observed": False,
                            "blocked_reason_class": "cdp_renderer_input_surface_not_observed",
                            "renderer_surface_blocked_reason_class": "cdp_renderer_input_surface_not_observed",
                            "cdp_localhost_only": True,
                            "cdp_target_bound_to_custom_launch": True,
                            "cdp_editable_surface_observed": False,
                        },
                        {
                            "native_window_usable": True,
                            "input_capable_ui_observed": True,
                            "blocked_reason_class": "",
                            "native_app_usability_source": "cdp_renderer_input_capable_ui",
                            "cdp_localhost_only": True,
                            "cdp_target_bound_to_custom_launch": True,
                            "cdp_editable_surface_observed": True,
                        },
                    ],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
                mock.patch("wild_boar_proxy.native_window_probe.time.sleep"),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["real_codex_app_launched"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(packet["post_launch_usability_recheck_attempted"])
        self.assertEqual(packet["post_launch_usability_recheck_status"], "ok")
        self.assertEqual(
            packet["post_launch_usability_recheck_machine_error_code"],
            "OK",
        )
        self.assertEqual(packet["post_launch_usability_recheck_attempt_count"], 1)
        self.assertEqual(packet["native_app_usability_source"], "cdp_renderer_input_capable_ui")

    def test_live_custom_native_launch_accepts_input_capable_renderer_as_runtime_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                        "launcher_stdout_path": str(layout.launcher_stdout),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 222,
                        "blocked_reason_class": "",
                        "window_visible": True,
                        "window_frontmost": True,
                        "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                        "native_app_usability_source": "cdp_renderer_input_capable_ui",
                        "cdp_localhost_only": True,
                        "cdp_target_bound_to_custom_launch": True,
                        "cdp_editable_surface_observed": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": False,
                        "runtime_ready_source": "launcher_stdout_markers",
                        "runtime_ready_stdout_paths_checked": [str(layout.launcher_stdout)],
                        "runtime_ready_markers": list(native_probe.RUNTIME_READY_STDOUT_MARKERS),
                        "runtime_ready_missing_markers": list(native_probe.RUNTIME_READY_STDOUT_MARKERS),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=temp_root / "profiles",
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["real_codex_app_launched"])
        self.assertTrue(packet["runtime_ready_observed"])
        self.assertTrue(packet["runtime_ready_renderer_fallback_used"])
        self.assertEqual(
            packet["runtime_ready_source"],
            "cdp_pid_bound_input_capable_renderer",
        )
        self.assertEqual(packet["runtime_ready_missing_markers"], [])

    def test_live_custom_native_launch_uses_observed_stable_config_fallback_when_generated_missing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            managed_dir = temp_root / "managed"
            managed_dir.mkdir()
            stable_config = temp_root / "config.yaml"
            stable_config.write_text("api-keys:\n  - local-token\n", encoding="utf-8")
            generated_config = managed_dir / "stable-runtime-config.generated.yaml"
            launcher_stdout = temp_root / "launcher.stdout.log"
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=launcher_stdout,
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=managed_dir,
                        stable_config=stable_config,
                        stable_runtime_generated_config_file=generated_config,
                    ),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.emit_local_token",
                    side_effect=AssertionError("generated token path should not be used"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.emit_local_token_from_config_path",
                    return_value="local-token",
                ) as token_reader,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.materialize_probe_profile",
                    return_value={"profile_dir": str(layout.profile_dir)},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                        "launcher_stdout_path": str(launcher_stdout),
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value={
                        "root_app_pids": [222],
                        "custom_process_lines": [
                            "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                        ],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 222,
                        "blocked_reason_class": "",
                        "window_visible": True,
                        "window_frontmost": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                        "native_app_usability_source": "cdp_renderer_input_capable_ui",
                        "cdp_localhost_only": True,
                        "cdp_target_bound_to_custom_launch": True,
                        "cdp_editable_surface_observed": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": True,
                        "runtime_ready_source": "launcher_stdout_markers",
                        "runtime_ready_stdout_paths_checked": [str(launcher_stdout)],
                        "runtime_ready_markers": list(native_probe.RUNTIME_READY_STDOUT_MARKERS),
                        "runtime_ready_missing_markers": [],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
                mock.patch("wild_boar_proxy.native_window_probe.time.sleep"),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                    persistent_profile_base_dir=temp_root / "profiles",
                )

        token_reader.assert_called_once_with(stable_config)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["observed_stable_config_fallback_used"])
        self.assertFalse(packet["stable_runtime_generated_config_file_present"])
        self.assertFalse(packet["stable_runtime_generated_config_default_present"])
        self.assertTrue(packet["observed_stable_config_file_present"])
        self.assertTrue(packet["token_config_file_present"])
        self.assertEqual(
            packet["token_config_source_kind"],
            "observed_stable_config_fallback",
        )
        self.assertEqual(
            packet["local_token_source_kind"],
            "observed_stable_config_fallback",
        )

    def test_live_custom_native_launch_blocks_when_process_dies_after_initial_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": False,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={"native_window_usable": True, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertTrue(packet["process_started"])
        self.assertFalse(packet["process_still_observed_after_wait"])
        self.assertTrue(packet["process_exited_after_start"])
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_PROCESS_EXITED_AFTER_START")
        self.assertEqual(packet["next_action"], "relaunch_custom_codex_after_process_exit")

    def test_live_custom_native_launch_reports_startup_loader_stuck_without_fake_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 222,
                        "blocked_reason_class": "",
                        "window_visible": True,
                        "window_frontmost": True,
                        "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "input_capable_ui_observed": False,
                        "blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                        "renderer_surface_blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                        "native_app_usability_source": "cdp_renderer_startup_loader_without_editable_surface",
                        "renderer_startup_loader_observed": True,
                        "renderer_mounted": False,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_reload_app_page_for_pid",
                    return_value=native_probe._renderer_recovery_packet(
                        status="blocked",
                        machine_error_code="CDP_PAGE_RELOAD_FAILED",
                        reason_class="cdp_page_reload_failed",
                        reload_targets=[],
                    ),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_RENDERER_STARTUP_LOADER_STUCK")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertTrue(packet["running_status"])
        self.assertTrue(packet["native_window_process_kept_running"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["input_capable_ui_observed"])
        self.assertTrue(packet["renderer_startup_loader_observed"])
        self.assertFalse(packet["renderer_mounted"])
        self.assertTrue(packet["renderer_recovery_attempted"])
        self.assertEqual(packet["renderer_recovery_status"], "blocked")
        self.assertEqual(
            packet["renderer_recovery_packet"]["machine_error_code"],
            "CDP_PAGE_RELOAD_FAILED",
        )
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "cdp_renderer_startup_loader_stuck",
        )
        self.assertEqual(packet["next_action"], "stop_and_diagnose_custom_renderer_startup_loader")

    def test_live_custom_native_launch_recovers_startup_loader_after_bounded_cdp_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            observed_window = {
                "window_observed": True,
                "observed_pid": 222,
                "blocked_reason_class": "",
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                "window_query": "Codex\ttrue\ttrue\tfalse\t1\t120,80\t1320,820",
                "custom_window_candidate_pids": [222],
            }
            startup_usability = {
                "native_window_usable": False,
                "input_capable_ui_observed": False,
                "blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                "renderer_surface_blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                "native_app_usability_source": "cdp_renderer_startup_loader_without_editable_surface",
                "renderer_startup_loader_observed": True,
                "renderer_mounted": False,
            }
            recovered_usability = {
                "native_window_usable": True,
                "input_capable_ui_observed": True,
                "blocked_reason_class": "",
                "native_app_usability_source": "cdp_renderer_input_capable_ui",
                "cdp_localhost_only": True,
                "cdp_endpoint_redacted": True,
                "cdp_target_bound_to_custom_launch": True,
                "cdp_editable_surface_observed": True,
                "raw_dom_exposed": False,
                "raw_ax_tree_exposed": False,
                "browser_cdp_authority_widened": False,
                "renderer_startup_loader_observed": False,
                "renderer_mounted": True,
            }
            launch_result = {
                "custom_process_observed": True,
                "custom_process_still_observed_after_wait": True,
                "post_observation_wait_seconds": 2.0,
                "startup_inventory": {
                    "root_app_pids": [222],
                    "custom_process_lines": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                    "sample": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                },
                "launcher_pid": 222,
                "launcher_stdout_path": str(layout.launcher_stdout),
            }
            reload_packet = native_probe._renderer_recovery_packet(
                status="ok",
                machine_error_code="OK",
                reason_class="ok",
                reload_targets=[
                    {
                        "target_url": "app://-/index.html",
                        "target_type": "page",
                        "reload_ok": True,
                        "error_class": "",
                    }
                ],
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value=launch_result,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=launch_result["startup_inventory"],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[observed_window, observed_window],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    side_effect=[startup_usability, recovered_usability],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._apply_codex_desktop_auth_blocker",
                    side_effect=lambda packet, **_: packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_reload_app_page_for_pid",
                    return_value=reload_packet,
                ) as reload_app_page,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": True,
                        "runtime_ready_source": "test",
                        "runtime_ready_stdout_paths_checked": [],
                        "runtime_ready_markers": [],
                        "runtime_ready_missing_markers": [],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
                mock.patch("wild_boar_proxy.native_window_probe.time.sleep") as sleep,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=temp_root / "profiles",
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["real_codex_app_launched"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(packet["input_capable_ui_observed"])
        self.assertFalse(packet["renderer_startup_loader_observed"])
        self.assertTrue(packet["renderer_mounted"])
        self.assertTrue(packet["renderer_recovery_attempted"])
        self.assertEqual(packet["renderer_recovery_status"], "ok")
        self.assertEqual(packet["renderer_recovery_action"], "cdp_page_reload")
        self.assertEqual(packet["native_app_usability_source"], "cdp_renderer_input_capable_ui")
        self.assertEqual(packet["next_action"], "none")
        reload_app_page.assert_called_once_with(
            222,
            port=int(native_probe.CODEX_REMOTE_DEBUGGING_PORT),
            allowed_owner_pids=[222],
        )
        sleep.assert_called_once_with(native_probe.CODEX_RENDERER_RECOVERY_WAIT_SECONDS)

    def test_live_custom_native_launch_preserves_proven_window_when_recovery_recheck_regresses(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            observed_window = {
                "window_observed": True,
                "observed_pid": 222,
                "blocked_reason_class": "",
                "window_visible": True,
                "window_frontmost": True,
                "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                "window_query_method": "Electron/Sentry window lifecycle scope",
                "custom_window_candidate_pids": [222],
            }
            regressed_window = {
                "window_observed": False,
                "observed_pid": 333,
                "blocked_reason_class": "pid_visible_but_accessible_window_absent",
                "window_visible": False,
                "window_frontmost": False,
                "window_bounds": {},
                "window_query_method": "AX/System Events process window count",
                "custom_window_candidate_pids": [222],
            }
            startup_usability = {
                "native_window_usable": False,
                "input_capable_ui_observed": False,
                "blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                "renderer_surface_blocked_reason_class": "cdp_renderer_startup_loader_stuck",
                "native_app_usability_source": "cdp_renderer_startup_loader_without_editable_surface",
                "renderer_startup_loader_observed": True,
                "renderer_mounted": False,
                "cdp_target_bound_to_custom_launch": True,
            }
            launch_result = {
                "custom_process_observed": True,
                "custom_process_still_observed_after_wait": True,
                "post_observation_wait_seconds": 2.0,
                "startup_inventory": {
                    "root_app_pids": [222],
                    "custom_process_lines": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                    "sample": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                },
                "launcher_pid": 222,
                "launcher_stdout_path": str(layout.launcher_stdout),
            }
            reload_packet = native_probe._renderer_recovery_packet(
                status="ok",
                machine_error_code="OK",
                reason_class="ok",
                reload_targets=[
                    {
                        "target_url": "app://-/index.html",
                        "target_type": "page",
                        "reload_ok": True,
                        "error_class": "",
                    }
                ],
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.materialize_probe_profile",
                    return_value={"profile_dir": str(layout.profile_dir)},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value=launch_result,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=launch_result["startup_inventory"],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    side_effect=[observed_window, regressed_window],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    side_effect=[startup_usability, startup_usability],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._apply_codex_desktop_auth_blocker",
                    side_effect=lambda packet, **_: packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._cdp_reload_app_page_for_pid",
                    return_value=reload_packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": True,
                        "runtime_ready_source": "test",
                        "runtime_ready_stdout_paths_checked": [],
                        "runtime_ready_markers": [],
                        "runtime_ready_missing_markers": [],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._post_launch_usability_recheck_candidate",
                    return_value=False,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.time.sleep"),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    keep_running_on_window_observed=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_RENDERER_STARTUP_LOADER_STUCK",
        )
        self.assertTrue(packet["native_window_observed"])
        self.assertTrue(packet["running_status"])
        self.assertTrue(packet["native_window_process_kept_running"])
        self.assertTrue(packet["renderer_recovery_attempted"])
        self.assertEqual(packet["renderer_recovery_status"], "ok")
        self.assertEqual(
            packet["renderer_surface_blocked_reason_class"],
            "cdp_renderer_startup_loader_stuck",
        )

    def test_live_custom_native_launch_blocks_if_existing_same_profile_process_survives(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={
                        "custom_processes_gone": False,
                        "initial_custom_pids": [222],
                    },
                ),
                mock.patch("wild_boar_proxy.native_window_probe.launch_native_candidate") as launch_native_candidate,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_PRELAUNCH_PROCESS_STOP_FAILED")
        self.assertTrue(packet["prelaunch_existing_custom_process_stop_attempted"])
        self.assertFalse(packet["prelaunch_existing_custom_processes_gone"])
        self.assertEqual(packet["prelaunch_existing_custom_process_initial_pids"], [222])
        self.assertFalse(packet["process_started"])
        launch_native_candidate.assert_not_called()

    def test_live_custom_native_launch_stops_same_profile_process_then_launches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.build_configured_model_availability_packet",
                    return_value=advertised_model_packet("gpt-5.3-codex"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={
                        "custom_processes_gone": True,
                        "initial_custom_pids": [222],
                    },
                ) as terminate_custom,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [333],
                            "custom_process_lines": ["redacted"],
                            "sample": ["redacted"],
                        },
                        "launcher_pid": 333,
                    },
                ) as launch_native_candidate,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._wait_for_window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "window_visible": True,
                        "window_frontmost": True,
                        "observed_pid": 333,
                        "blocked_reason_class": "",
                        "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={"native_window_usable": True, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={"runtime_ready_observed": True, "runtime_ready_source": "test"},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=profile_base,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["prelaunch_existing_custom_process_stop_attempted"])
        self.assertTrue(packet["prelaunch_existing_custom_processes_gone"])
        self.assertEqual(packet["prelaunch_existing_custom_process_initial_pids"], [222])
        self.assertTrue(packet["process_started"])
        self.assertTrue(packet["new_launch_started"])
        self.assertTrue(packet["native_window_observed"])
        self.assertTrue(packet["native_app_usable"])
        self.assertTrue(packet["real_codex_app_launched"])
        self.assertFalse(packet["current_codex_touched"])
        self.assertFalse(packet["current_original_profile_shortcut_used"])
        self.assertFalse(packet.get("asar_touched", False))
        terminate_custom.assert_called_once()
        launch_native_candidate.assert_called_once()

    def test_live_custom_native_launch_reuses_existing_window_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.build_configured_model_availability_packet",
                    return_value=advertised_model_packet("gpt-5.3-codex"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value={"custom_process_count": 1},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.show_custom_native_window_packet",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "custom_process_pid": 222,
                        "custom_window_observed": True,
                        "custom_window_visible": True,
                        "custom_window_frontmost": True,
                        "custom_window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "native_app_usable": True,
                        "input_capable_ui_observed": True,
                        "native_app_usability_source": "input_capable_ui",
                    },
                ) as show_window,
                mock.patch("wild_boar_proxy.native_window_probe.terminate_custom_processes") as terminate,
                mock.patch("wild_boar_proxy.native_window_probe.launch_native_candidate") as launch_native,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=profile_base,
                    reuse_existing_window_if_present=True,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["existing_custom_window_detected"])
        self.assertTrue(packet["existing_custom_window_reused"])
        self.assertTrue(packet["reused_existing_window"])
        self.assertEqual(packet["launch_origin"], "existing_window")
        self.assertFalse(packet["fresh_launch_started"])
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["process_started"])
        self.assertTrue(packet["native_window_observed"])
        self.assertTrue(packet["native_app_usable"])
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertEqual(packet["custom_process_pid"], 222)
        self.assertEqual(packet["cleanup_result"]["status"], "existing_window_reused")
        show_window.assert_called_once()
        terminate.assert_not_called()
        launch_native.assert_not_called()

    def test_live_custom_native_launch_existing_visible_but_unusable_is_not_downgraded_to_visibility_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.emit_local_token",
                    return_value="local-token",
                ),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.build_configured_model_availability_packet",
                    return_value=advertised_model_packet("gpt-5.3-codex"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value={"custom_process_count": 1},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.show_custom_native_window_packet",
                    return_value={
                        "status": "blocked",
                        "machine_error_code": "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN",
                        "custom_process_pid": 222,
                        "custom_window_observed": True,
                        "custom_window_visible": True,
                        "custom_window_frontmost": True,
                        "custom_window_bounds": {
                            "x": 120,
                            "y": 80,
                            "width": 1320,
                            "height": 820,
                        },
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": False,
                        "native_app_usable": False,
                        "input_capable_ui_observed": False,
                        "native_app_usability_source": "not_proven",
                        "native_app_usability_blocked_reason_class": (
                            "input_capable_window_not_proven_for_pid"
                        ),
                    },
                ) as show_window,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes"
                ) as terminate,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate"
                ) as launch_native,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                    persistent_profile_base_dir=profile_base,
                    reuse_existing_window_if_present=True,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CUSTOM_NATIVE_EXISTING_WINDOW_USABILITY_NOT_PROVEN",
        )
        self.assertTrue(packet["running_status"])
        self.assertTrue(packet["expected_custom_identity_observed"])
        self.assertTrue(packet["native_window_observed"])
        self.assertTrue(packet["custom_window_visible"])
        self.assertTrue(packet["custom_window_frontmost"])
        self.assertFalse(packet["native_app_usable"])
        self.assertFalse(packet["existing_custom_window_reused"])
        self.assertFalse(packet["reused_existing_window"])
        self.assertEqual(packet["launch_origin"], "existing_window_unproven")
        self.assertEqual(packet["cleanup_result"]["status"], "existing_process_left_running")
        self.assertIn("visible", packet["human_message"])
        self.assertIn("input-capable UI was not proven", packet["human_message"])
        show_window.assert_called_once()
        terminate.assert_not_called()
        launch_native.assert_not_called()

    def test_live_custom_native_launch_uses_stable_persistent_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"

            def launch_packet() -> dict[str, object]:
                with (
                    mock.patch(
                        "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                        return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                    ),
                    mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                    mock.patch(
                        "wild_boar_proxy.native_filesystem_probe.build_configured_model_availability_packet",
                        return_value=advertised_model_packet("wbp-deepseek-v4-pro-max"),
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                        return_value={
                            "status": "ok",
                            "machine_error_code": "OK",
                            "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                            "isolated_default_keychain_verified": True,
                            "isolated_search_list_verified": True,
                        },
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe.launch_native_candidate",
                        return_value={
                            "custom_process_observed": True,
                            "custom_process_still_observed_after_wait": True,
                            "post_observation_wait_seconds": 2.0,
                            "startup_inventory": {
                                "root_app_pids": [222],
                                "custom_process_lines": [
                                    "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                                ],
                                "sample": [
                                    "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                                ],
                            },
                            "launcher_pid": 222,
                        },
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                        return_value={
                            "window_observed": True,
                            "observed_pid": 222,
                            "blocked_reason_class": "",
                            "window_visible": True,
                            "window_frontmost": True,
                            "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                        },
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                        return_value={
                            "native_window_usable": True,
                            "blocked_reason_class": "",
                        },
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe._build_identity_binding",
                        return_value={"status": "ok", "window_bound_to_custom_launch": True},
                    ),
                    mock.patch(
                        "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                        return_value={
                            "runtime_ready_observed": True,
                            "runtime_ready_source": "test",
                            "runtime_ready_stdout_paths_checked": [],
                            "runtime_ready_markers": [],
                            "runtime_ready_missing_markers": [],
                        },
                    ),
                ):
                    return launch_custom_native_app_packet(
                        repo_root=ROOT,
                        endpoint="http://127.0.0.1:8318/v1",
                        model="wbp-deepseek-v4-pro-max",
                        owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                        persistent_profile_base_dir=profile_base,
                    )

            first = launch_packet()
            second = launch_packet()
            profile_root = Path(str(first["persistent_profile_root"]))
            profile_files_exist = {
                "config": (profile_root / "config.toml").exists(),
                "auth": (profile_root / "auth.json").exists(),
                "launcher": (profile_root / "codex-custom-launch.sh").exists(),
            }

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(first["profile_mode"], "persistent_custom")
        self.assertEqual(first["persistent_profile_id"], "wbp-custom-main")
        self.assertEqual(first["persistent_profile_root"], second["persistent_profile_root"])
        self.assertEqual(first["persistent_codex_home"], second["persistent_codex_home"])
        self.assertEqual(first["persistent_user_data_dir"], second["persistent_user_data_dir"])
        self.assertFalse(first["temp_profile_used"])
        self.assertFalse(second["temp_profile_used"])
        self.assertTrue(first["history_persistence_expected"])
        self.assertFalse(first["visible_thread_history_restored_proven"])
        self.assertFalse(first["cleanup_deletes_persistent_profile_by_default"])
        self.assertFalse(first["browser_client_path_authority"])
        self.assertFalse(first["original_codex_profile_runtime_dependency"])
        self.assertEqual(
            profile_files_exist,
            {"config": True, "auth": True, "launcher": True},
        )

    def test_live_custom_native_launch_blocks_when_keychain_preflight_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "blocked",
                        "machine_error_code": "KEYCHAIN_PREFLIGHT_WRITE_SURFACE_BLOCKED",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": False,
                        "isolated_search_list_verified": False,
                    },
                ),
                mock.patch("wild_boar_proxy.native_window_probe.launch_native_candidate") as launch_native_candidate,
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_PREFLIGHT_WRITE_SURFACE_BLOCKED")
        self.assertEqual(packet["next_action"], "stop_and_diagnose_keychain_preflight")
        self.assertTrue(packet["keychain_preflight_attempted"])
        self.assertEqual(packet["keychain_preflight_status"], "blocked")
        self.assertEqual(packet["prompt_avoidance_claim_scope"], "keychain_not_found_prompt_only")
        self.assertFalse(packet["real_user_keychain_modified"])
        self.assertFalse(packet["process_started"])
        launch_native_candidate.assert_not_called()

    def test_live_custom_native_launch_keeps_launch_truth_when_keychain_preflight_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "failed",
                        "machine_error_code": "KEYCHAIN_PREFLIGHT_VERIFY_DEFAULT_FAILED",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": False,
                        "isolated_search_list_verified": False,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_NOT_PROVEN")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertTrue(packet["keychain_preflight_attempted"])
        self.assertEqual(packet["keychain_preflight_status"], "failed")
        self.assertEqual(
            packet["keychain_preflight_reason_code"],
            "KEYCHAIN_PREFLIGHT_VERIFY_DEFAULT_FAILED",
        )
        self.assertFalse(packet["isolated_default_keychain_verified"])
        self.assertEqual(packet["prompt_avoidance_claim_scope"], "keychain_not_found_prompt_only")
        self.assertFalse(packet["real_user_keychain_modified"])
        self.assertFalse(packet["keychain_item_read"])
        self.assertFalse(packet["keychain_reset_performed"])

    def test_live_custom_native_launch_reports_launcher_exit_before_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_filesystem_probe.build_configured_model_availability_packet",
                    return_value=advertised_model_packet("gpt-5.3-codex"),
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": False,
                        "custom_process_still_observed_after_wait": False,
                        "post_observation_wait_seconds": 0,
                        "startup_inventory": {
                            "root_app_pids": [],
                            "custom_process_lines": [],
                            "sample": [],
                        },
                        "launcher_pid": 222,
                        "launcher_exit_code_early": 9,
                    },
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_LAUNCHER_EXIT_NONZERO")
        self.assertTrue(packet["new_launch_started"])
        self.assertFalse(packet["process_started"])
        self.assertEqual(packet["launcher_exit_code_early"], 9)
        self.assertTrue(packet["launcher_failed_before_custom_process"])
        self.assertEqual(packet["next_action"], "stop_and_diagnose_custom_native_launcher")

    def test_live_custom_native_launch_keeps_skipped_preflight_as_quiet_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(managed_dir=temp_root, stable_config=temp_root / "stable.json"),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "skipped",
                        "machine_error_code": "KEYCHAIN_PREFLIGHT_NO_DEFAULT_KEYCHAIN",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": False,
                        "isolated_search_list_verified": False,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value={
                        "custom_process_observed": True,
                        "custom_process_still_observed_after_wait": True,
                        "post_observation_wait_seconds": 2.0,
                        "startup_inventory": {
                            "root_app_pids": [222],
                            "custom_process_lines": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                            "sample": [
                                "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                            ],
                        },
                        "launcher_pid": 222,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={"window_observed": True, "observed_pid": 222, "blocked_reason_class": ""},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": False,
                        "blocked_reason_class": "input_capable_window_not_proven_for_pid",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.3-codex",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_NOT_PROVEN")
        self.assertFalse(packet["real_codex_app_launched"])
        self.assertTrue(packet["keychain_preflight_attempted"])
        self.assertEqual(packet["keychain_preflight_status"], "skipped")
        self.assertEqual(
            packet["keychain_preflight_reason_code"],
            "KEYCHAIN_PREFLIGHT_NO_DEFAULT_KEYCHAIN",
        )
        self.assertEqual(packet["prompt_avoidance_claim_scope"], "keychain_not_found_prompt_only")
        self.assertFalse(packet["isolated_default_keychain_verified"])
        self.assertFalse(packet["isolated_search_list_verified"])
        self.assertFalse(packet["real_user_keychain_modified"])
        self.assertFalse(packet["keychain_item_read"])
        self.assertFalse(packet["keychain_reset_performed"])

    def test_live_custom_native_launch_prefers_stability_inventory_for_window_probe(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                tmp_root=temp_root / "tmp",
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            launch_result = {
                "custom_process_observed": True,
                "custom_process_still_observed_after_wait": True,
                "post_observation_wait_seconds": 2.0,
                "startup_inventory": {
                    "root_app_pids": [111],
                    "custom_process_lines": [
                        "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                    "sample": [
                        "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data"
                    ],
                },
                "stability_inventory": {
                    "root_app_pids": [111],
                    "custom_process_lines": [
                        "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                    "sample": [
                        "111 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                },
                "launcher_pid": 222,
                "remote_debugging_port": int(native_probe.CODEX_REMOTE_DEBUGGING_PORT),
                "remote_debugging_port_source": "allocated_loopback_launch_port",
                "remote_debugging_port_file_written": True,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.create_persistent_custom_profile_layout",
                    return_value=layout,
                ),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value=launch_result,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._wait_for_window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 333,
                        "window_visible": True,
                        "window_frontmost": True,
                        "window_bounds": {},
                        "blocked_reason_class": "",
                    },
                ) as wait_for_window,
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._apply_codex_desktop_auth_blocker",
                    side_effect=lambda packet, **_: packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": True,
                        "runtime_ready_source": "test",
                        "runtime_ready_stdout_paths_checked": [],
                        "runtime_ready_markers": [],
                        "runtime_ready_missing_markers": [],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "ok")
        wait_for_window.assert_called_once_with(
            launch_result["stability_inventory"],
            profile_dir=layout.profile_dir,
        )

    def test_live_custom_native_launch_focuses_root_pid_when_window_not_yet_observed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            layout = SimpleNamespace(
                custom_user_data_dir=temp_root / "electron-user-data",
                custom_home_dir=temp_root / "profile" / "home",
                profile_dir=temp_root / "profile",
                launcher_stdout=temp_root / "launcher.stdout.log",
                launcher_stderr=temp_root / "launcher.stderr.log",
                launcher_path=temp_root / "launcher.sh",
            )
            launch_result = {
                "custom_process_observed": True,
                "custom_process_still_observed_after_wait": True,
                "post_observation_wait_seconds": 2.0,
                "startup_inventory": {
                    "root_app_pids": [222],
                    "custom_process_lines": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                    "sample": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                },
                "stability_inventory": {
                    "root_app_pids": [222],
                    "custom_process_lines": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                    "sample": [
                        "222 /Applications/Codex.app/Contents/MacOS/Codex --user-data-dir=/tmp/custom/electron-user-data",
                        "333 /Applications/Codex.app/Contents/Frameworks/Codex Helper.app/Contents/MacOS/Codex Helper --type=renderer --user-data-dir=/tmp/custom/electron-user-data",
                    ],
                },
                "launcher_pid": 222,
                "remote_debugging_port": int(native_probe.CODEX_REMOTE_DEBUGGING_PORT),
                "remote_debugging_port_source": "allocated_loopback_launch_port",
                "remote_debugging_port_file_written": True,
            }
            with (
                mock.patch(
                    "wild_boar_proxy.native_window_probe.RuntimePaths.from_env",
                    return_value=SimpleNamespace(
                        managed_dir=temp_root,
                        stable_config=temp_root / "stable.json",
                    ),
                ),
                mock.patch("wild_boar_proxy.native_window_probe.emit_local_token", return_value="local-token"),
                mock.patch("wild_boar_proxy.native_window_probe.create_native_probe_layout", return_value=layout),
                mock.patch("wild_boar_proxy.native_window_probe.materialize_probe_profile", return_value={"profile_dir": str(layout.profile_dir)}),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.prepare_isolated_home_keychain",
                    return_value={
                        "status": "ok",
                        "machine_error_code": "OK",
                        "prompt_avoidance_claim_scope": "keychain_not_found_prompt_only",
                        "isolated_default_keychain_verified": True,
                        "isolated_search_list_verified": True,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.terminate_custom_processes",
                    return_value={"custom_processes_gone": True, "initial_custom_pids": []},
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe.launch_native_candidate",
                    return_value=launch_result,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._wait_for_window_observation_via_ax",
                    return_value={
                        "window_observed": False,
                        "observed_pid": 333,
                        "window_visible": False,
                        "window_frontmost": False,
                        "window_bounds": {},
                        "blocked_reason_class": "pid_visible_but_accessible_window_absent",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._focus_custom_window_by_pid",
                    return_value={
                        "window_focus_action_attempted": True,
                        "window_focus_action_succeeded": True,
                        "window_focus_observed_pid": 222,
                        "window_focus_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                    },
                ) as focus_window,
                mock.patch(
                    "wild_boar_proxy.native_window_probe.collect_codex_process_inventory",
                    return_value=launch_result["stability_inventory"],
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_observation_via_ax",
                    return_value={
                        "window_observed": True,
                        "observed_pid": 222,
                        "window_visible": True,
                        "window_frontmost": True,
                        "window_bounds": {"x": 120, "y": 80, "width": 1320, "height": 820},
                        "blocked_reason_class": "",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._window_usability_from_observation",
                    return_value={
                        "native_window_usable": True,
                        "input_capable_ui_observed": True,
                        "blocked_reason_class": "",
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._apply_codex_desktop_auth_blocker",
                    side_effect=lambda packet, **_: packet,
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._runtime_ready_from_launcher_stdout",
                    return_value={
                        "runtime_ready_observed": True,
                        "runtime_ready_source": "test",
                        "runtime_ready_stdout_paths_checked": [],
                        "runtime_ready_markers": [],
                        "runtime_ready_missing_markers": [],
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.native_window_probe._build_identity_binding",
                    return_value={"status": "ok", "window_bound_to_custom_launch": True},
                ),
            ):
                packet = launch_custom_native_app_packet(
                    repo_root=ROOT,
                    endpoint="http://127.0.0.1:8318/v1",
                    model="gpt-5.5",
                    owner_authorization_phrase=OWNER_STANDING_AUTHORIZATION_PHRASE,
                )

        self.assertEqual(packet["status"], "ok")
        focus_window.assert_called_once_with(222)

    def test_authorization_blocks_without_owner_authorization(self) -> None:
        packet = build_native_dispatch_authorization_packet(
            owner_authorized=False,
            admission_packet=admitted_custom_packet(),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_DISPATCH_OWNER_AUTHORIZATION_MISSING",
        )
        self.assertFalse(packet["live_dispatch_allowed"])
        self.assertEqual(packet["blocked_reason_class"], "owner_authorization_missing")

    def test_authorization_blocks_without_admitted_custom_preflight(self) -> None:
        packet = build_native_dispatch_authorization_packet(
            owner_authorized=True,
            admission_packet={"status": "blocked", "admitted": False},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_DISPATCH_ADMISSION_NOT_ADMITTED")

    def test_custom_dispatch_blocked_packet_does_not_attempt_dispatch(self) -> None:
        packet = build_native_custom_dispatch_blocked_packet(
            owner_authorized=False,
            admission_packet=admitted_custom_packet(),
        )

        self.assertEqual(packet["packet_kind"], "native_custom_dispatch_blocked")
        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["process_observed"])
        self.assertFalse(packet["window_observed"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertFalse(packet["route_trace_bound"])

    def test_custom_dispatch_full_slice_pass_with_window_observed_still_not_complete(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={
                "before_snapshot_captured": True,
                "after_snapshot_captured": True,
                "current_codex_touched": False,
            },
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dispatch_slice_pass"])
        self.assertTrue(packet["dispatch_observed"])
        self.assertTrue(packet["process_observed"])
        self.assertTrue(packet["window_observed"])
        self.assertTrue(packet["isolated_app_support_dir_used"])
        self.assertTrue(packet["isolated_cache_dir_used"])
        self.assertTrue(packet["isolated_runtime_dir_used"])
        self.assertTrue(packet["keychain_reset_prompt_blocker_planned"])
        self.assertTrue(packet["native_window_usable"])
        self.assertTrue(packet["native_window_usable_claimed"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertFalse(packet["route_trace_bound"])
        self.assertFalse(packet["route_inference_attempted"])

    def test_custom_dispatch_accepts_honest_window_observation_blocked_reason(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={
                "window_observed": False,
                "blocked_reason_class": "os_window_query_unavailable",
            },
            usability_observation={
                "native_window_usable": False,
                "native_window_usable_claimed": False,
                "blocked_reason_class": "window_usability_unclassifiable_without_os_window",
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["window_observation_blocked_with_reason"])
        self.assertEqual(
            packet["window_observation_blocked_reason_class"],
            "os_window_query_unavailable",
        )
        self.assertTrue(packet["usability_blocked_with_reason"])
        self.assertIn("native_window_usability_required", packet["failed_checks"])
        self.assertFalse(packet["native_launch_complete"])

    def test_custom_dispatch_blocks_process_only_proof(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": False},
            usability_observation={"native_window_usable": False},
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("window_observation_or_blocked_reason_required", packet["failed_checks"])
        self.assertFalse(packet["native_launch_complete"])

    def test_custom_dispatch_requires_carried_isolation_and_server_route_plan(self) -> None:
        admitted = admitted_custom_packet()
        admitted["isolated_home_plan"] = False
        admitted["isolated_codex_home_plan"] = False
        admitted["isolated_profile_data_dir_plan"] = False
        admitted["isolated_app_support_dir_plan"] = False
        admitted["isolated_cache_dir_plan"] = False
        admitted["isolated_runtime_dir_plan"] = False
        admitted["keychain_reset_prompt_blocker_plan"] = False
        admitted["server_planned_route_endpoint"] = False

        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted,
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("custom_requires_isolated_home_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_codex_home_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_profile_data_dir_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_app_support_dir_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_cache_dir_plan", packet["failed_checks"])
        self.assertIn("custom_requires_isolated_runtime_dir_plan", packet["failed_checks"])
        self.assertIn(
            "custom_requires_keychain_reset_prompt_blocker_plan",
            packet["failed_checks"],
        )
        self.assertIn("custom_requires_server_planned_route_endpoint", packet["failed_checks"])

    def test_custom_dispatch_blocks_cleanup_failure(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "blocked"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("cleanup_or_rollback_ok_required", packet["failed_checks"])

    def test_custom_dispatch_blocks_current_codex_touch(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": True},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("current_codex_must_remain_untouched", packet["failed_checks"])

    def test_observation_packets_do_not_claim_prompt_or_routing(self) -> None:
        process = build_native_process_observation_packet(
            dispatch_observed=True,
            process_observed=True,
        )
        window = build_native_window_observation_packet(window_observed=True)
        usability = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=True,
        )

        self.assertEqual(process["status"], "ok")
        self.assertFalse(process["native_launch_complete"])
        self.assertFalse(process["prompt_attempted"])
        self.assertFalse(process["route_trace_bound"])
        self.assertEqual(window["status"], "ok")
        self.assertFalse(window["native_window_usable"])
        self.assertFalse(window["native_window_usable_claimed"])
        self.assertFalse(window["native_launch_complete"])
        self.assertEqual(usability["status"], "ok")
        self.assertTrue(usability["native_window_usable"])
        self.assertTrue(usability["native_window_usable_claimed"])
        self.assertFalse(usability["prompt_attempted"])
        self.assertFalse(usability["route_trace_bound"])
        self.assertFalse(usability["native_launch_complete"])

    def test_window_observation_requires_window_or_blocked_reason(self) -> None:
        packet = build_native_window_observation_packet(window_observed=False)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_WINDOW_OBSERVATION_MISSING")

    def test_window_usability_requires_usability_or_blocked_reason(self) -> None:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_WINDOW_USABILITY_NOT_PROVEN")

    def test_window_usability_accepts_honest_blocked_reason(self) -> None:
        packet = build_native_window_usability_packet(
            window_observed=False,
            input_capable_ui_observed=False,
            blocked_reason_class="owner_authorization_missing",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["native_window_usable"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertEqual(packet["blocked_reason_class"], "owner_authorization_missing")

    def test_current_codex_protection_requires_before_after_and_untouched(self) -> None:
        packet = build_native_current_codex_protection_packet(
            before_snapshot_captured=True,
            after_snapshot_captured=False,
            current_codex_touched=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["current_codex_protected"])

    def test_current_codex_protection_accepts_no_live_dispatch_basis(self) -> None:
        packet = build_native_current_codex_protection_packet(
            before_snapshot_captured=False,
            after_snapshot_captured=False,
            current_codex_touched=False,
            protection_basis="no_live_dispatch_attempted",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["current_codex_protected"])
        self.assertEqual(packet["protection_basis"], "no_live_dispatch_attempted")

    def test_cleanup_rollback_packet_requires_ok_status(self) -> None:
        packet = build_native_cleanup_rollback_execution_packet(
            cleanup_attempted=True,
            rollback_attempted=False,
            cleanup_or_rollback_status="blocked",
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_CLEANUP_ROLLBACK_NOT_OK")

    def test_cleanup_rollback_accepts_no_process_launched_status(self) -> None:
        packet = build_native_cleanup_rollback_execution_packet(
            cleanup_attempted=False,
            rollback_attempted=False,
            cleanup_or_rollback_status="ok_no_process_launched",
            cleanup_blocked_reason_class="owner_authorization_missing_no_live_dispatch",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["cleanup_or_rollback_status"], "ok_no_process_launched")
        self.assertEqual(
            packet["cleanup_blocked_reason_class"],
            "owner_authorization_missing_no_live_dispatch",
        )

    def test_original_deferred_packet_preserves_boundary_without_reversibility_claim(self) -> None:
        packet = build_native_original_dispatch_deferred_packet()

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["original_contract_preserved"])
        self.assertFalse(packet["original_live_dispatch_attempted"])
        self.assertEqual(packet["reason_class"], "out_of_scope_custom_first")
        self.assertFalse(packet["route_trace_bound"])
        self.assertFalse(packet["reversibility_proof_claimed"])

    def test_false_green_audit_rejects_upgrade_claims(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        custom["native_launch_complete"] = True
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["machine_error_code"], "NATIVE_DISPATCH_FALSE_GREEN")

    def test_false_green_audit_passes_for_bounded_dispatch_and_deferred_original(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "ok")
        self.assertTrue(audit["original_deferred_honestly"])
        self.assertTrue(audit["no_prompt_attempted"])
        self.assertTrue(audit["no_route_inference_attempted"])
        self.assertTrue(audit["native_window_usability_bounded"])
        self.assertTrue(audit["usability_not_upgraded_to_prompt_or_route"])

    def test_false_green_audit_rejects_usability_without_process_and_window(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": False},
            window_observation={"window_observed": False, "blocked_reason_class": "os_window_query_unavailable"},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["machine_error_code"], "NATIVE_DISPATCH_FALSE_GREEN")


if __name__ == "__main__":
    unittest.main()
