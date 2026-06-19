# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import official_e2e_working_flow_proof_runner as runner
from wild_boar_proxy.core import packets


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_codex_working_flow_delivery_proof import (  # noqa: E402
    PROMPT,
)
from test_official_e2e_working_flow_proof_join import (  # noqa: E402
    _assert_no_raw_prompt_route_or_provider,
    _assert_no_ui_native_or_product_claim,
    _assert_no_writes,
    _packet as _join_packet,
    _positive_pair,
    _secret_values,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs_payload(
    *,
    real_hook_file: str = "real-hook.json",
    delivery_join_file: str = "delivery-join.json",
    proof_run_id: str = "WBP_REPEATABLE_E2E_RUN_001",
    expected_real_hook_sha256: str = "a" * 64,
    expected_delivery_join_sha256: str = "b" * 64,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND,
        "proof_run_id": proof_run_id,
        "real_custom_hook_proof_file": real_hook_file,
        "official_working_flow_delivery_join_file": delivery_join_file,
        "expected_real_custom_hook_proof_file_sha256": expected_real_hook_sha256,
        "expected_official_working_flow_delivery_join_file_sha256": (
            expected_delivery_join_sha256
        ),
    }


class OfficialE2EWorkingFlowProofRunnerTests(unittest.TestCase):
    def test_positive_runs_join_from_declared_relative_manifest_files(self) -> None:
        real_hook, delivery = _positive_pair()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "real-hook.json", real_hook)
            _write_json(root / "delivery-join.json", delivery)
            _write_json(
                root / "runner-inputs.json",
                _inputs_payload(
                    expected_real_hook_sha256=_file_sha256(root / "real-hook.json"),
                    expected_delivery_join_sha256=_file_sha256(root / "delivery-join.json"),
                ),
            )

            packet = runner.run_official_e2e_working_flow_proof_runner_command(
                inputs_file=str(root / "runner-inputs.json"),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["packet_kind"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND,
        )
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["runner_inputs_valid"])
        self.assertTrue(packet["official_e2e_join_valid"])
        self.assertTrue(packet["official_e2e_working_flow_proven"])
        self.assertTrue(packet["custom_codex_hook_to_official_working_flow_bound"])
        self.assertTrue(packet["custom_codex_flow_origin_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["hook_event_digest_bound_to_working_flow"])
        self.assertTrue(packet["hook_thread_or_turn_digest_bound_to_working_flow"])
        self.assertTrue(packet["hook_session_digest_bound_to_working_flow"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["official_e2e_runner_inputs_file_path_recorded"])
        self.assertEqual(len(packet["official_e2e_runner_inputs_file_sha256"]), 64)
        self.assertTrue(packet["real_custom_hook_proof_file_sha256_bound_to_runner_inputs"])
        self.assertTrue(
            packet["official_working_flow_delivery_join_file_sha256_bound_to_runner_inputs"]
        )
        self.assertEqual(
            packet["expected_real_custom_hook_proof_file_sha256"],
            packet["observed_real_custom_hook_proof_file_sha256"],
        )
        self.assertEqual(
            packet["expected_official_working_flow_delivery_join_file_sha256"],
            packet["observed_official_working_flow_delivery_join_file_sha256"],
        )
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_build_blocks_manifest_secret_material_without_recording_value(self) -> None:
        payload = _inputs_payload()
        payload["debug_secret_payload"] = PROMPT
        packet = runner.build_official_e2e_working_flow_proof_runner_packet(
            runner_inputs_packet=payload,
            official_e2e_join_packet=_join_packet(),
            file_metadata={
                "official_e2e_runner_inputs_file_read": True,
                "official_e2e_runner_inputs_file_valid_json": True,
                "official_e2e_runner_inputs_file_mapping": True,
                "official_e2e_runner_inputs_file_path_recorded": False,
                "official_e2e_runner_inputs_file_sha256": "a" * 64,
                "real_custom_hook_proof_file_sha256": "a" * 64,
                "official_working_flow_delivery_join_file_sha256": "b" * 64,
            },
            secret_values=_secret_values(),
        )

        serialized = json.dumps(packet, sort_keys=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE,
        )
        self.assertIn("runner_inputs_unknown_fields", packet["blocking_reasons"])
        self.assertIn("runner_inputs_secret_material_present", packet["blocking_reasons"])
        self.assertFalse(packet["official_e2e_join_valid"])
        self.assertNotIn(PROMPT, serialized)
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(packet, secret_values=_secret_values()),
            [],
        )

    def test_build_blocks_secret_only_input_without_false_green_join_valid(self) -> None:
        payload = _inputs_payload()
        packet = runner.build_official_e2e_working_flow_proof_runner_packet(
            runner_inputs_packet=payload,
            official_e2e_join_packet=_join_packet(),
            file_metadata={
                "official_e2e_runner_inputs_file_read": True,
                "official_e2e_runner_inputs_file_valid_json": True,
                "official_e2e_runner_inputs_file_mapping": True,
                "official_e2e_runner_inputs_file_path_recorded": False,
                "official_e2e_runner_inputs_file_sha256": "a" * 64,
                "real_custom_hook_proof_file_sha256": "a" * 64,
                "official_working_flow_delivery_join_file_sha256": "b" * 64,
            },
            secret_values=[str(payload["proof_run_id"])],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE,
        )
        self.assertEqual(packet["runner_input_failures"], [])
        self.assertEqual(
            packet["runner_unsafe_failures"],
            ["runner_inputs_secret_material_present"],
        )
        self.assertFalse(packet["official_e2e_join_valid"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[str(payload["proof_run_id"])],
            ),
            [],
        )

    def test_runner_does_not_call_join_when_manifest_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs_file = root / "runner-inputs.json"
            _write_json(
                inputs_file,
                {
                    **_inputs_payload(),
                    "packet_kind": "wrong",
                },
            )

            with mock.patch(
                "wild_boar_proxy.official_e2e_working_flow_proof_runner."
                "run_official_e2e_working_flow_proof_join_command"
            ) as join_command:
                packet = runner.run_official_e2e_working_flow_proof_runner_command(
                    inputs_file=str(inputs_file),
                )

        join_command.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn("runner_inputs_packet_kind_invalid", packet["blocking_reasons"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_raw_prompt_manifest_before_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs_file = root / "runner-inputs.json"
            _write_json(
                inputs_file,
                {
                    **_inputs_payload(),
                    "raw_prompt": "do not store this",
                },
            )

            with mock.patch(
                "wild_boar_proxy.official_e2e_working_flow_proof_runner."
                "run_official_e2e_working_flow_proof_join_command"
            ) as join_command:
                packet = runner.run_official_e2e_working_flow_proof_runner_command(
                    inputs_file=str(inputs_file),
                )

        join_command.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertIn("runner_inputs_unknown_fields", packet["blocking_reasons"])
        self.assertIn("runner_inputs_raw_prompt_not_allowed", packet["blocking_reasons"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_missing_declared_evidence_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "runner-inputs.json", _inputs_payload())

            packet = runner.run_official_e2e_working_flow_proof_runner_command(
                inputs_file=str(root / "runner-inputs.json"),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertFalse(packet["runner_inputs_valid"])
        self.assertFalse(packet["official_e2e_join_valid"])
        self.assertIn(
            "real_custom_hook_proof_file_sha256_not_bound_to_runner_inputs",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "official_working_flow_delivery_join_file_sha256_not_bound_to_runner_inputs",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_real_hook_file_sha_mismatch_before_join(self) -> None:
        real_hook, delivery = _positive_pair()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "real-hook.json", real_hook)
            _write_json(root / "delivery-join.json", delivery)
            _write_json(
                root / "runner-inputs.json",
                _inputs_payload(
                    expected_real_hook_sha256="0" * 64,
                    expected_delivery_join_sha256=_file_sha256(root / "delivery-join.json"),
                ),
            )

            with mock.patch(
                "wild_boar_proxy.official_e2e_working_flow_proof_runner."
                "run_official_e2e_working_flow_proof_join_command"
            ) as join_command:
                packet = runner.run_official_e2e_working_flow_proof_runner_command(
                    inputs_file=str(root / "runner-inputs.json"),
                )

        join_command.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn(
            "real_custom_hook_proof_file_sha256_not_bound_to_runner_inputs",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["real_custom_hook_proof_file_sha256_bound_to_runner_inputs"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_delivery_join_file_sha_mismatch_before_join(self) -> None:
        real_hook, delivery = _positive_pair()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "real-hook.json", real_hook)
            _write_json(root / "delivery-join.json", delivery)
            _write_json(
                root / "runner-inputs.json",
                _inputs_payload(
                    expected_real_hook_sha256=_file_sha256(root / "real-hook.json"),
                    expected_delivery_join_sha256="0" * 64,
                ),
            )

            with mock.patch(
                "wild_boar_proxy.official_e2e_working_flow_proof_runner."
                "run_official_e2e_working_flow_proof_join_command"
            ) as join_command:
                packet = runner.run_official_e2e_working_flow_proof_runner_command(
                    inputs_file=str(root / "runner-inputs.json"),
                )

        join_command.assert_not_called()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn(
            "official_working_flow_delivery_join_file_sha256_not_bound_to_runner_inputs",
            packet["blocking_reasons"],
        )
        self.assertFalse(
            packet["official_working_flow_delivery_join_file_sha256_bound_to_runner_inputs"]
        )
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_digest_mismatch_from_join(self) -> None:
        real_hook, delivery = _positive_pair()
        delivery = dict(delivery)
        delivery["working_flow_source_prompt_digest"] = "0" * 64

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "real-hook.json", real_hook)
            _write_json(root / "delivery-join.json", delivery)
            _write_json(
                root / "runner-inputs.json",
                _inputs_payload(
                    expected_real_hook_sha256=_file_sha256(root / "real-hook.json"),
                    expected_delivery_join_sha256=_file_sha256(root / "delivery-join.json"),
                ),
            )

            packet = runner.run_official_e2e_working_flow_proof_runner_command(
                inputs_file=str(root / "runner-inputs.json"),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_JOIN_INVALID,
        )
        self.assertIn("prompt_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_runner_blocks_join_with_unsafe_product_claim(self) -> None:
        real_hook, delivery = _positive_pair()
        delivery = {**delivery, "product_ready": True}

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_json(root / "real-hook.json", real_hook)
            _write_json(root / "delivery-join.json", delivery)
            _write_json(
                root / "runner-inputs.json",
                _inputs_payload(
                    expected_real_hook_sha256=_file_sha256(root / "real-hook.json"),
                    expected_delivery_join_sha256=_file_sha256(root / "delivery-join.json"),
                ),
            )

            packet = runner.run_official_e2e_working_flow_proof_runner_command(
                inputs_file=str(root / "runner-inputs.json"),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_JOIN_INVALID,
        )
        self.assertIn("delivery_product_ready", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["official_e2e_working_flow_proven"])
        _assert_no_ui_native_or_product_claim(self, packet)
        _assert_no_writes(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_runner_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "official-e2e-working-flow-proof-runner",
                "--inputs-file",
                "runner-inputs.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")

    def test_cli_emits_runner_packet(self) -> None:
        expected = runner.build_official_e2e_working_flow_proof_runner_packet(
            runner_inputs_packet=_inputs_payload(),
            official_e2e_join_packet=_join_packet(),
            file_metadata={
                "official_e2e_runner_inputs_file_read": True,
                "official_e2e_runner_inputs_file_valid_json": True,
                "official_e2e_runner_inputs_file_mapping": True,
                "official_e2e_runner_inputs_file_path_recorded": False,
                "official_e2e_runner_inputs_file_sha256": "a" * 64,
                "real_custom_hook_proof_file_sha256": "a" * 64,
                "official_working_flow_delivery_join_file_sha256": "b" * 64,
            },
            secret_values=_secret_values(),
        )
        stdout = io.StringIO()

        with (
            mock.patch(
                "wild_boar_proxy.cli.run_official_e2e_working_flow_proof_runner_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "official-e2e-working-flow-proof-runner",
                    "--inputs-file",
                    "runner-inputs.json",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertTrue(payload["official_e2e_working_flow_proven"])
        run_command.assert_called_once_with(inputs_file="runner-inputs.json")
        self.assertEqual(packets.inspect_command_packet_semantics(payload), [])


if __name__ == "__main__":
    unittest.main()
