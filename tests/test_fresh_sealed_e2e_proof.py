# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import fresh_sealed_e2e_proof as fresh_sealed
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.native_window_probe import (
    OWNER_STANDING_AUTHORIZATION_PHRASE as OWNER_AUTHORIZATION_PHRASE,
)


TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_custom_codex_admission import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    ROUTE_ID,
    _paths,
    _write_fake_codex,
    _write_profile,
)
from test_custom_codex_ui_visibility_proof import _native_packet  # noqa: E402


FRESHNESS_ANCHOR_DIGEST = "a" * 64
OTHER_FRESHNESS_ANCHOR_DIGEST = "b" * 64


def _fake_native_packet(**kwargs: object) -> dict[str, object]:
    return _native_packet(
        expected_text=str(kwargs["expected_text"]),
        request_id=str(kwargs["request_id"]),
    )


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class FreshSealedE2EProofTests(unittest.TestCase):
    def test_positive_runs_fresh_live_to_full_runtime_admission_and_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")

            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "PYTHONPATH": str(ROOT),
                        "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_native_ui_observer_proof_command",
                    side_effect=_fake_native_packet,
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "_new_freshness_anchor_digest",
                    return_value=FRESHNESS_ANCHOR_DIGEST,
                ),
            ):
                packet = fresh_sealed.run_fresh_sealed_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

            final_file = root / "proof" / "fresh-sealed-e2e-proof.packet.json"
            persisted = json.loads(final_file.read_text(encoding="utf-8"))
            changed_names = {Path(path).name for path in packet["changed_files"]}

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            fresh_sealed.FRESH_SEALED_E2E_PACKET_KIND,
        )
        self.assertEqual(packet, persisted)
        self.assertTrue(packet["fresh_sealed_e2e_proven"])
        self.assertTrue(packet["fresh_runtime_proof_sealed"])
        self.assertTrue(packet["core_dispatch_proven"])
        self.assertTrue(packet["core_runtime_proof_sealed"])
        self.assertFalse(packet["core_dispatch_requires_native_ui_visibility"])
        self.assertFalse(packet["core_dispatch_requires_full_runtime_dispatch"])
        self.assertFalse(packet["ui_visibility_required_for_core"])
        self.assertFalse(packet["full_runtime_required_for_core"])
        self.assertTrue(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertTrue(packet["full_runtime_diagnostics_passed"])
        self.assertEqual(packet["full_runtime_diagnostic_blocking_reasons"], [])
        self.assertEqual(
            packet["full_runtime_ui_visibility_proof_source"],
            "native_custom_codex_visible_flow_proof",
        )
        self.assertTrue(packet["full_runtime_dispatch_runner_proven"])
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertTrue(packet["native_custom_codex_visible_flow_proven"])
        self.assertEqual(
            packet["custom_codex_ui_visibility_source"],
            "native_custom_codex_visible_flow_proof",
        )
        self.assertTrue(packet["strict_admission_proven"])
        self.assertTrue(packet["external_freshness_proven"])
        self.assertTrue(packet["proof_admission_sealed"])
        self.assertTrue(packet["feature_runtime_proof_sealed"])
        self.assertTrue(packet["wrong_digest_negative_proven"])
        self.assertEqual(packet["freshness_anchor_digest"], FRESHNESS_ANCHOR_DIGEST)
        self.assertTrue(packet["freshness_anchor_bound_to_runner"])
        self.assertTrue(packet["freshness_anchor_bound_to_admission"])
        self.assertTrue(packet["freshness_anchor_bound_to_seal"])
        self.assertEqual(packet["ui_visibility_source"], "auto_native_observer")
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_product_ready"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["native_free_chat_router_product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["runtime_effective_truth_written"])
        self.assertTrue(packet["evidence_written"])
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertFalse(packet["proof_dir_path_recorded"])
        self.assertFalse(packet["input_file_paths_recorded"])
        self.assertIn("fresh-live-e2e-proof.packet.json", changed_names)
        self.assertIn("visible-source-binding-proof.packet.json", changed_names)
        self.assertIn("native-ui-observer.packet.json", changed_names)
        self.assertIn("native-custom-codex-visible-flow-proof.packet.json", changed_names)
        self.assertIn("custom-codex-ui-visibility-proof.packet.json", changed_names)
        self.assertIn("strict-admission.packet.json", changed_names)
        self.assertIn("admission-seal.packet.json", changed_names)
        self.assertIn("wrong-digest-admission-seal.packet.json", changed_names)
        self.assertIn("fresh-sealed-e2e-proof.packet.json", changed_names)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_core_dispatch_proof_succeeds_when_native_ui_visibility_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            blocked_ui = packets.build_command_packet(
                ok=False,
                human_message="UI visibility blocked by test.",
                machine_error_code="WBP_TEST_UI_VISIBILITY_BLOCKED",
                liveness="not_applicable",
                severity="recoverable",
                operator_action="stop",
                changed_files=[],
                effect="probe",
                extra={
                    "packet_kind": "wbp_custom_codex_ui_visibility_proof",
                    "custom_codex_ui_visibility_proven": False,
                    "product_ready": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                    "native_codex_subagent_used_as_dip": False,
                    "raw_prompt_recorded": False,
                    "raw_route_id_recorded": False,
                    "raw_provider_response_recorded": False,
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                    "blocking_reasons": ["test_ui_visibility_blocked"],
                },
            )

            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "PYTHONPATH": str(ROOT),
                        "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_native_ui_observer_proof_command",
                    return_value=_native_packet(
                        expected_text="wrong",
                        request_id="wrong",
                        overrides={
                            "status": "error",
                            "machine_error_code": "WBP_TEST_NATIVE_UI_BLOCKED",
                            "custom_response_exact_token_observed": False,
                            "custom_response_bound_to_request": False,
                            "blocking_reasons": ["test_native_ui_blocked"],
                        },
                    ),
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_custom_codex_ui_visibility_proof_command",
                    return_value=blocked_ui,
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "_new_freshness_anchor_digest",
                    return_value=FRESHNESS_ANCHOR_DIGEST,
                ),
            ):
                packet = fresh_sealed.run_fresh_sealed_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["fresh_sealed_e2e_proven"])
        self.assertTrue(packet["core_dispatch_proven"])
        self.assertTrue(packet["core_runtime_proof_sealed"])
        self.assertTrue(packet["fresh_live_custom_codex_e2e_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_custom_codex_visible_flow_proven"])
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertFalse(packet["full_runtime_required_for_core"])
        self.assertTrue(packet["full_runtime_diagnostics_attempted"])
        self.assertFalse(packet["full_runtime_diagnostics_passed"])
        self.assertIn(
            "fresh_sealed_e2e_full_runtime_not_proven",
            packet["full_runtime_diagnostic_blocking_reasons"],
        )
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_product_ready"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["native_free_chat_router_product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_wrong_digest_green_from_downstream_blocks_final_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")

            original_seal = fresh_sealed.run_full_runtime_dispatch_admission_seal_command

            def seal_side_effect(**kwargs: object) -> dict[str, object]:
                packet = original_seal(**kwargs)
                if kwargs["expected_freshness_anchor_digest"] == OTHER_FRESHNESS_ANCHOR_DIGEST:
                    packet = dict(packet)
                    packet["status"] = "ok"
                    packet["machine_error_code"] = "OK"
                    packet["proof_admission_sealed"] = True
                    packet["feature_runtime_proof_sealed"] = True
                    packet["external_freshness_proven"] = True
                    packet["blocking_reasons"] = []
                return packet

            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "PYTHONPATH": str(ROOT),
                        "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                    },
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_native_ui_observer_proof_command",
                    side_effect=_fake_native_packet,
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "_new_freshness_anchor_digest",
                    return_value=FRESHNESS_ANCHOR_DIGEST,
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_full_runtime_dispatch_admission_seal_command",
                    side_effect=seal_side_effect,
                ),
            ):
                packet = fresh_sealed.run_fresh_sealed_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["fresh_sealed_e2e_proven"])
        self.assertTrue(packet["fresh_runtime_proof_sealed"])
        self.assertTrue(packet["core_dispatch_proven"])
        self.assertFalse(packet["wrong_digest_negative_proven"])
        self.assertIn(
            "fresh_sealed_e2e_wrong_digest_negative_not_proven",
            packet["full_runtime_diagnostic_blocking_reasons"],
        )
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_product_ready"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["native_free_chat_router_product_ready"])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_fresh_live_failure_stops_before_seal_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            failed = packets.build_command_packet(
                ok=False,
                human_message="fresh live failed",
                machine_error_code="WBP_TEST_FRESH_LIVE_FAILED",
                liveness="network_dependent",
                severity="recoverable",
                operator_action="stop",
                changed_files=[],
                effect="mutate",
                extra={
                    "schema_version": 1,
                    "packet_kind": "wbp_fresh_live_custom_codex_e2e_proof",
                    "fresh_live_custom_codex_e2e_proven": False,
                    "user_prompt_submit_hook_ran": False,
                    "api_lane_called": False,
                    "dispatch_proven": False,
                    "codex_working_flow_delivery_proven": False,
                    "blocking_reasons": ["test_fresh_live_failed"],
                    "product_ready": False,
                    "state_written": False,
                    "runtime_effective_truth_written": False,
                    "evidence_written": True,
                    "file_mutation_attempted": True,
                },
            )

            with (
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_fresh_live_custom_codex_e2e_proof_command",
                    return_value=failed,
                ),
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_full_runtime_dispatch_proof_runner_command"
                ) as run_runner,
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_full_runtime_dispatch_admission_command"
                ) as run_admission,
                mock.patch(
                    "wild_boar_proxy.fresh_sealed_e2e_proof."
                    "run_full_runtime_dispatch_admission_seal_command"
                ) as run_seal,
            ):
                packet = fresh_sealed.run_fresh_sealed_e2e_proof_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    proof_dir=str(root / "proof"),
                    expected_text=EXPECTED_TEXT,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            fresh_sealed.FRESH_SEALED_E2E_FRESH_LIVE_FAILED,
        )
        self.assertFalse(packet["fresh_sealed_e2e_proven"])
        self.assertFalse(packet["fresh_runtime_proof_sealed"])
        self.assertFalse(packet["full_runtime_dispatch_runner_proven"])
        self.assertFalse(packet["strict_admission_proven"])
        self.assertFalse(packet["proof_admission_sealed"])
        run_runner.assert_not_called()
        run_admission.assert_not_called()
        run_seal.assert_not_called()
        self.assertIn(
            "fresh_sealed_e2e_fresh_live_not_proven",
            packet["blocking_reasons"],
        )

    def test_core_dispatch_false_claim_matrix_blocks_core_proof(self) -> None:
        base = {
            "status": "ok",
            "machine_error_code": "OK",
            "packet_kind": fresh_sealed.FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
            "fresh_live_custom_codex_e2e_proven": True,
            "user_prompt_submit_hook_ran": True,
            "api_lane_called": True,
            "dispatch_proven": True,
            "codex_working_flow_delivery_proven": True,
            "fallback_used": False,
            "local_imitation_used": False,
            "native_codex_subagent_used_as_dip": False,
            "product_ready": False,
        }
        cases = [
            ("user_prompt_submit_hook_ran", False),
            ("api_lane_called", False),
            ("dispatch_proven", False),
            ("codex_working_flow_delivery_proven", False),
            ("fallback_used", True),
            ("local_imitation_used", True),
            ("native_codex_subagent_used_as_dip", True),
            ("product_ready", True),
        ]
        for key, value in cases:
            packet = dict(base)
            packet[key] = value
            with self.subTest(key=key):
                self.assertFalse(fresh_sealed._fresh_live_ok(packet))

    def test_cli_effect_classifier_marks_fresh_sealed_runner_as_mutate(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "codex-runner",
                "fresh-sealed-e2e-proof",
                "--prompt",
                "hi",
                "--codex-model",
                "gpt-5.4",
                "--custom-codex-ui-visibility-proof-file",
                "/tmp/wbp-ui-proof.json",
                "--observer-timeout-seconds",
                "45",
                "--native-auto-launch-custom-codex",
                "--native-auto-launch-owner-authorization-phrase",
                OWNER_AUTHORIZATION_PHRASE,
                "--json",
            ]
        )

        self.assertEqual(args.codex_runner_command, "fresh-sealed-e2e-proof")
        self.assertEqual(args.codex_model, "gpt-5.4")
        self.assertEqual(
            args.custom_codex_ui_visibility_proof_file,
            "/tmp/wbp-ui-proof.json",
        )
        self.assertEqual(args.observer_timeout_seconds, 45.0)
        self.assertTrue(args.native_auto_launch_custom_codex)
        self.assertEqual(
            args.native_auto_launch_owner_authorization_phrase,
            OWNER_AUTHORIZATION_PHRASE,
        )
        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")

    def test_cli_emits_fresh_sealed_packet(self) -> None:
        expected = packets.build_command_packet(
            ok=True,
            human_message="fresh sealed ok",
            machine_error_code="OK",
            liveness="network_dependent",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            effect="mutate",
            extra={
                "schema_version": 1,
                "packet_kind": fresh_sealed.FRESH_SEALED_E2E_PACKET_KIND,
                "fresh_sealed_e2e_proven": True,
                "fresh_runtime_proof_sealed": True,
                "product_ready": False,
                "state_written": False,
                "runtime_effective_truth_written": False,
                "evidence_written": True,
                "file_mutation_attempted": True,
                "blocking_reasons": [],
            },
        )
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_fresh_sealed_e2e_proof_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "codex-runner",
                    "fresh-sealed-e2e-proof",
                    "--prompt",
                    "hi",
                    "--codex-model",
                    "gpt-5.4",
                    "--proof-dir",
                    "proof",
                    "--codex-cwd",
                    str(ROOT),
                    "--custom-codex-ui-visibility-proof-file",
                    "/tmp/wbp-ui-proof.json",
                    "--observer-timeout-seconds",
                    "45",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["fresh_sealed_e2e_proven"])
        run_command.assert_called_once_with(
            paths=mock.ANY,
            prompt_text="hi",
            custom_codex_ui_visibility_proof_file="/tmp/wbp-ui-proof.json",
            codex_bin=None,
            codex_model="gpt-5.4",
            proof_dir="proof",
            codex_cwd=str(ROOT),
            expected_text="WBP_DIP_DISPATCH_OK",
            sandbox="danger-full-access",
            timeout_seconds=300,
            persistent_profile_id="wbp-custom-main",
            persistent_profile_base_dir=None,
            observer_timeout_seconds=45.0,
            native_auto_launch_custom_codex=False,
            native_auto_launch_endpoint="http://127.0.0.1:8318/v1",
            native_auto_launch_model="gpt-5.5",
            native_auto_launch_owner_authorization_phrase=None,
            native_auto_launch_repo_root=None,
            native_auto_launch_stable_runtime_generated_config_file=None,
        )
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
