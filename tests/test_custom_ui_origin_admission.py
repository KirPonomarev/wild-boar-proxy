# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import io
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import custom_ui_origin_admission as admission
from wild_boar_proxy import real_custom_app_submit_ledger_proof as submit_proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


PROMPT = "Codex, дай задачу DIP: fixture prompt"
ROUTE_ID = "deepseek-fixture-route"


def _write_app(root: Path, name: str, bundle_id: str) -> Path:
    app = root / name
    contents = app / "Contents"
    contents.mkdir(parents=True)
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump({"CFBundleIdentifier": bundle_id}, handle)
    return app


def _submit_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "custom submit proof",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "packet_kind": submit_proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "real_custom_app_submit_ledger_proven": True,
        "custom_app_submit_proven": True,
        "custom_app_submit_ledger_gate_proven": True,
        "real_user_prompt_submit_ledger_proven": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "ledger_newer_than_pre_submit_snapshot": True,
        "process_inventory_live": True,
        "wbp_clean_app_process_observed": True,
        "wbp_clean_app_server_process_observed": True,
        "stock_codex_app_process_observed": False,
        "api_lane_called": False,
        "api_response_received": False,
        "dispatch_attempted": False,
        "dispatch_proven": False,
        "route_bound_dispatch_proven": False,
        "provider_response_proven": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "native_free_chat_router_proven": False,
        "live_provider_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": [],
    }
    packet.update(overrides)
    return packet


def _packet(
    *,
    stock_bundle_id: str = "com.openai.codex",
    custom_bundle_id: str = "com.kirill.codexcustom",
    submit_packet: dict[str, object] | None = None,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        stock_app = _write_app(root, "Codex.app", stock_bundle_id)
        custom_app = _write_app(root, "Codex WBP Clean.app", custom_bundle_id)
        profile_dir = root / "profile"
        user_data_dir = profile_dir / "electron-user-data"
        user_data_dir.mkdir(parents=True)
        launcher = profile_dir / "codex-custom-launch.sh"
        launcher.write_text("#!/bin/sh\n", encoding="utf-8")
        with mock.patch.object(
            admission,
            "attest_official_codex_app",
            return_value={
                "status": "ok",
                "machine_error_code": "OK",
                "team_id_proven": True,
                "codesign_valid": True,
            },
        ):
            return admission.build_custom_ui_origin_admission_packet(
                custom_app_submit_packet=_submit_packet()
                if submit_packet is None
                else submit_packet,
                prompt_text=PROMPT,
                stock_app_path=stock_app,
                custom_app_path=custom_app,
                custom_profile_dir=profile_dir,
                custom_user_data_dir=user_data_dir,
                custom_launcher_path=launcher,
            )


def _shared_official_packet() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        app = _write_app(root, "ChatGPT.app", "com.openai.codex")
        profile_dir = root / "profile"
        user_data_dir = profile_dir / "electron-user-data"
        user_data_dir.mkdir(parents=True)
        launcher = profile_dir / "codex-custom-launch.sh"
        launcher.write_text("#!/bin/sh\n", encoding="utf-8")
        with mock.patch.object(
            admission,
            "attest_official_codex_app",
            return_value={
                "status": "ok",
                "machine_error_code": "OK",
                "team_id_proven": True,
                "codesign_valid": True,
            },
        ):
            return admission.build_custom_ui_origin_admission_packet(
                custom_app_submit_packet=_submit_packet(
                    stock_codex_app_process_observed=True,
                ),
                prompt_text=PROMPT,
                stock_app_path=app,
                custom_app_path=app,
                custom_profile_dir=profile_dir,
                custom_user_data_dir=user_data_dir,
                custom_launcher_path=launcher,
            )


def _fixture_paths(root: Path, *, custom_bundle_id: str = "com.kirill.codexcustom") -> tuple[Path, Path, Path, Path, Path]:
    stock_app = _write_app(root, "Codex.app", "com.openai.codex")
    custom_app = _write_app(root, "Codex WBP Clean.app", custom_bundle_id)
    profile_dir = root / "profile"
    user_data_dir = profile_dir / "electron-user-data"
    user_data_dir.mkdir(parents=True)
    launcher = profile_dir / "codex-custom-launch.sh"
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    return stock_app, custom_app, profile_dir, user_data_dir, launcher


def _assert_no_raw_prompt_route_or_product(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(PROMPT, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertFalse(packet_contains_text(packet, PROMPT))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class CustomUiOriginAdmissionTests(unittest.TestCase):
    def test_shared_official_bundle_admits_only_with_isolated_instance_proof(self) -> None:
        packet = _shared_official_packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["bundle_id_collision_detected"])
        self.assertFalse(packet["custom_app_identity_distinct"])
        self.assertTrue(packet["shared_official_native_bundle"])
        self.assertTrue(packet["stock_official_app_attested"])
        self.assertTrue(packet["stock_official_app_team_id_proven"])
        self.assertTrue(packet["stock_official_app_codesign_valid"])
        self.assertTrue(packet["custom_identity_isolated_by_profile"])
        self.assertTrue(packet["custom_instance_coexistence_possible"])
        self.assertTrue(packet["custom_instance_coexistence_proven"])
        self.assertTrue(packet["custom_ui_origin_admitted"])
        self.assertEqual(packet["blocking_reasons"], [])

    def test_unsigned_shared_bundle_id_lookalike_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            app = _write_app(root, "ChatGPT.app", "com.openai.codex")
            profile_dir = root / "profile"
            user_data_dir = profile_dir / "electron-user-data"
            user_data_dir.mkdir(parents=True)
            launcher = profile_dir / "codex-custom-launch.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            packet = admission.build_custom_ui_origin_admission_packet(
                custom_app_submit_packet=_submit_packet(
                    stock_codex_app_process_observed=True,
                ),
                prompt_text=PROMPT,
                stock_app_path=app,
                custom_app_path=app,
                custom_profile_dir=profile_dir,
                custom_user_data_dir=user_data_dir,
                custom_launcher_path=launcher,
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["shared_official_native_bundle"])
        self.assertFalse(packet["stock_official_app_attested"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertIn(
            "shared_official_native_bundle_not_attested",
            packet["blocking_reasons"],
        )

    def test_distinct_bundle_and_positive_fresh_submit_admits_origin_gate_only(self) -> None:
        packet = _packet()

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(
            packet["packet_kind"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND,
        )
        self.assertEqual(packet["stock_codex_bundle_id"], "com.openai.codex")
        self.assertEqual(packet["custom_codex_bundle_id"], "com.kirill.codexcustom")
        self.assertFalse(packet["bundle_id_collision_detected"])
        self.assertTrue(packet["custom_app_identity_distinct"])
        self.assertTrue(packet["custom_instance_coexistence_possible"])
        self.assertTrue(packet["custom_instance_coexistence_proven"])
        self.assertTrue(packet["fresh_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["custom_ui_origin_admitted"])
        self.assertTrue(packet["custom_codex_flow_origin_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["changed_files"], [])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_bundle_id_collision_blocks_even_with_positive_submit_packet(self) -> None:
        packet = _packet(custom_bundle_id="com.openai.codex")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_BUNDLE_ID_COLLISION,
        )
        self.assertTrue(packet["bundle_id_collision_detected"])
        self.assertFalse(packet["custom_app_identity_distinct"])
        self.assertFalse(packet["custom_instance_coexistence_possible"])
        self.assertFalse(packet["custom_instance_coexistence_proven"])
        self.assertTrue(packet["fresh_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertIn("bundle_id_collision_detected", packet["blocking_reasons"])
        self.assertIn(
            "custom_instance_coexistence_not_possible",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_stale_submit_ledger_blocks_origin_even_with_distinct_bundle(self) -> None:
        packet = _packet(
            submit_packet=_submit_packet(
                status="error",
                machine_error_code=(
                    submit_proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_STALE
                ),
                real_custom_app_submit_ledger_proven=False,
                custom_app_submit_proven=False,
                custom_app_submit_ledger_gate_proven=False,
                ledger_newer_than_pre_submit_snapshot=False,
                blocking_reasons=[
                    "hook_ledger_not_newer_than_pre_submit_snapshot"
                ],
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_LEDGER_NOT_PROVEN,
        )
        self.assertFalse(packet["fresh_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_instance_coexistence_proven"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertIn("custom_app_submit_packet_not_ok", packet["blocking_reasons"])
        self.assertIn(
            "fresh_user_prompt_submit_ledger_not_proven",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_provided_process_inventory_file_cannot_green_origin_admission(self) -> None:
        packet = _packet(
            submit_packet=_submit_packet(
                status="error",
                machine_error_code=(
                    submit_proof.REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN
                ),
                real_custom_app_submit_ledger_proven=False,
                custom_app_submit_proven=False,
                custom_app_submit_ledger_gate_proven=False,
                process_inventory_live=False,
                blocking_reasons=["process_inventory_not_live"],
            )
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_LEDGER_NOT_PROVEN,
        )
        self.assertFalse(packet["process_inventory_live"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertIn("custom_process_inventory_not_live", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_custom_submit_overclaim_blocks_origin_admission(self) -> None:
        packet = _packet(submit_packet=_submit_packet(product_ready=True))

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        self.assertIn(
            "custom_app_submit_must_not_claim_product_ready",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_custom_bundle_identifier_blocks_as_invalid(self) -> None:
        packet = _packet(custom_bundle_id="")

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_INVALID,
        )
        self.assertIn("custom_codex_bundle_id_missing", packet["blocking_reasons"])
        self.assertFalse(packet["custom_ui_origin_admitted"])
        _assert_no_raw_prompt_route_or_product(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_declared_paths_are_not_recorded_in_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stock_app, custom_app, profile_dir, user_data_dir, launcher = _fixture_paths(root)
            packet = admission.build_custom_ui_origin_admission_packet(
                custom_app_submit_packet=_submit_packet(
                    blocking_reasons=[
                        str(stock_app),
                        "machine_reason_token",
                    ],
                ),
                prompt_text=PROMPT,
                stock_app_path=stock_app,
                custom_app_path=custom_app,
                custom_profile_dir=profile_dir,
                custom_user_data_dir=user_data_dir,
                custom_launcher_path=launcher,
            )

            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)

            for path in (stock_app, custom_app, profile_dir, user_data_dir, launcher):
                self.assertNotIn(str(path), serialized)
            self.assertFalse(packet["stock_app_path_recorded"])
            self.assertFalse(packet["custom_app_path_recorded"])
            self.assertFalse(packet["custom_profile_dir_path_recorded"])
            self.assertFalse(packet["custom_user_data_dir_path_recorded"])
            self.assertFalse(packet["custom_launcher_path_recorded"])
            self.assertEqual(
                packet["custom_app_submit_blocking_reasons"],
                ["machine_reason_token"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_custom_ui_origin_admission_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "custom-ui-origin-admission",
                "--prompt",
                PROMPT,
                "--ledger-mtime-before-ns",
                "1",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_dispatch_emits_custom_ui_origin_admission_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stock_app, custom_app, profile_dir, user_data_dir, launcher = _fixture_paths(root)
            ledger = root / "ledger.json"
            ledger.write_text("{}", encoding="utf-8")
            stdout = io.StringIO()

            with (
                mock.patch(
                    "wild_boar_proxy.real_custom_app_submit_ledger_proof."
                    "run_real_user_prompt_submit_ledger_proof_command",
                    return_value=_submit_packet(
                        packet_kind="wbp_real_user_prompt_submit_ledger_proof",
                        real_user_prompt_submit_ledger_proven=True,
                        custom_app_submit_proven=False,
                        custom_app_submit_ledger_gate_proven=False,
                        real_custom_app_submit_ledger_proven=False,
                    ),
                ),
                mock.patch(
                    "wild_boar_proxy.real_custom_app_submit_ledger_proof."
                    "collect_codex_process_inventory",
                    return_value={
                        "sample": [
                            "222 /tmp/Codex WBP Clean.app/Contents/MacOS/Codex "
                            f"--user-data-dir={user_data_dir}",
                            "333 /tmp/Codex WBP Clean.app/Contents/Resources/"
                            "codex app-server",
                        ],
                        "custom_process_lines": [
                            "222 /tmp/Codex WBP Clean.app/Contents/MacOS/Codex"
                        ],
                        "default_process_lines": [],
                    },
                ),
                mock.patch("sys.stdout", stdout),
            ):
                exit_code = cli_mod.main(
                    [
                        "router-hook",
                        "custom-ui-origin-admission",
                        "--prompt",
                        PROMPT,
                        "--ledger-mtime-before-ns",
                        "0",
                        "--hook-ledger-file",
                        str(ledger),
                        "--stock-app-path",
                        str(stock_app),
                        "--custom-app-path",
                        str(custom_app),
                        "--custom-profile-dir",
                        str(profile_dir),
                        "--custom-user-data-dir",
                        str(user_data_dir),
                        "--custom-launcher-path",
                        str(launcher),
                        "--json",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(
            payload["packet_kind"],
            admission.CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND,
        )
        self.assertEqual(payload["effect"], "probe")
        self.assertFalse(payload["api_lane_called"])
        self.assertFalse(payload["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
