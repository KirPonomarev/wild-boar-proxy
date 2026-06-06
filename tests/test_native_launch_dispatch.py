# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import wild_boar_proxy.native_window_probe as native_probe
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


class NativeLaunchDispatchTests(unittest.TestCase):
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
        self.assertEqual(bounded["cdp_visible_input_candidate_count"], 1)
        self.assertFalse(bounded["cdp_text_value_captured"])
        self.assertFalse(bounded["cdp_prompt_attempted"])
        self.assertFalse(bounded["cdp_route_trace_bound"])

    def test_show_custom_native_window_focuses_only_wbp_profile_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            profile_base = temp_root / "profiles"
            user_data_dir = (
                profile_base / "wbp-custom-main" / "electron-user-data"
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
                ),
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
        self.assertEqual(packet["custom_window_bounds"]["x"], 120)
        self.assertFalse(packet["original_codex_touched"])
        self.assertFalse(packet["asar_touched"])
        focus.assert_called_once_with(222)

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

    def test_live_custom_native_launch_blocks_when_process_dies_after_initial_observation(self) -> None:
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
        self.assertEqual(packet["machine_error_code"], "CUSTOM_NATIVE_WINDOW_NOT_PROVEN")

    def test_live_custom_native_launch_blocks_if_existing_same_profile_process_survives(self) -> None:
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
        self.assertFalse(packet["new_launch_started"])
        self.assertFalse(packet["process_started"])
        self.assertTrue(packet["native_window_observed"])
        self.assertTrue(packet["native_app_usable"])
        self.assertEqual(packet["custom_process_pid"], 222)
        self.assertEqual(packet["cleanup_result"]["status"], "existing_window_reused")
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
