# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import full_runtime_dispatch_admission_seal as seal
from wild_boar_proxy.core import packets


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_full_runtime_dispatch_admission import (  # noqa: E402
    FRESHNESS_ANCHOR_DIGEST,
    OTHER_FRESHNESS_ANCHOR_DIGEST,
    _admit,
    _assert_no_raw_prompt_route_or_provider,
    _write_valid_proof,
)


def _seal(
    proof_dir: Path | str,
    *,
    expected_freshness_anchor_digest: str | None = FRESHNESS_ANCHOR_DIGEST,
) -> dict[str, object]:
    return seal.run_full_runtime_dispatch_admission_seal_command(
        proof_dir=str(proof_dir),
        expected_freshness_anchor_digest=expected_freshness_anchor_digest,
    )


def _canonical_sha256(packet: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            packet,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class FullRuntimeDispatchAdmissionSealTests(unittest.TestCase):
    def test_positive_seals_strict_fresh_admission_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir, runner_packet = _write_valid_proof(
                root,
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            before = {
                path.name: path.stat().st_mtime_ns for path in proof_dir.glob("*.json")
            }

            admission_packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            packet = _seal(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            after = {
                path.name: path.stat().st_mtime_ns for path in proof_dir.glob("*.json")
            }

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "read")
        self.assertEqual(
            packet["packet_kind"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_PACKET_KIND,
        )
        self.assertTrue(packet["proof_admission_sealed"])
        self.assertTrue(packet["feature_runtime_proof_sealed"])
        self.assertTrue(packet["admission_packet_present"])
        self.assertEqual(
            packet["admission_packet_kind"],
            "wbp_full_runtime_dispatch_admission",
        )
        self.assertEqual(
            packet["admission_packet_sha256"],
            _canonical_sha256(admission_packet),
        )
        self.assertTrue(packet["expected_freshness_anchor_digest_present"])
        self.assertEqual(
            packet["expected_freshness_anchor_digest"],
            FRESHNESS_ANCHOR_DIGEST,
        )
        self.assertTrue(packet["expected_freshness_anchor_digest_bound"])
        self.assertTrue(packet["external_freshness_proven"])
        self.assertTrue(packet["full_runtime_dispatch_runner_proven"])
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packet["handoff_payload_digest"], runner_packet["handoff_payload_digest"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_product_ready"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(before, after)
        _assert_no_raw_prompt_route_or_provider(self, packet, root)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_expected_freshness_digest_blocks_without_admission_call(self) -> None:
        with mock.patch(
            "wild_boar_proxy.full_runtime_dispatch_admission_seal."
            "run_full_runtime_dispatch_admission_command"
        ) as run_admission:
            packet = seal.run_full_runtime_dispatch_admission_seal_command(
                proof_dir="proof",
                expected_freshness_anchor_digest=None,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_INPUT_INVALID,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertFalse(packet["feature_runtime_proof_sealed"])
        self.assertFalse(packet["admission_packet_present"])
        self.assertIn(
            "expected_freshness_anchor_digest_missing",
            packet["blocking_reasons"],
        )
        run_admission.assert_not_called()

    def test_invalid_expected_freshness_digest_blocks_without_admission_call(self) -> None:
        with mock.patch(
            "wild_boar_proxy.full_runtime_dispatch_admission_seal."
            "run_full_runtime_dispatch_admission_command"
        ) as run_admission:
            packet = seal.run_full_runtime_dispatch_admission_seal_command(
                proof_dir="proof",
                expected_freshness_anchor_digest="not-a-digest",
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_INPUT_INVALID,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertIn(
            "expected_freshness_anchor_digest_invalid",
            packet["blocking_reasons"],
        )
        run_admission.assert_not_called()

    def test_wrong_expected_freshness_digest_blocks_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

            packet = _seal(
                proof_dir,
                expected_freshness_anchor_digest=OTHER_FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertFalse(packet["feature_runtime_proof_sealed"])
        self.assertTrue(packet["admission_packet_present"])
        self.assertTrue(packet["admission_packet_sha256"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn("admission_status_not_ok", packet["blocking_reasons"])
        self.assertIn("admission_machine_error_not_ok", packet["blocking_reasons"])
        self.assertIn(
            "admission_expected_freshness_anchor_digest_bound_not_true",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_old_non_fresh_proof_blocks_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))

            packet = _seal(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn(
            "admission_external_freshness_proven_not_true",
            packet["blocking_reasons"],
        )

    def test_unproven_admission_packet_blocks_without_false_green(self) -> None:
        admission_packet = {
            "status": "ok",
            "machine_error_code": "OK",
            "effect": "read",
            "packet_kind": "wbp_full_runtime_dispatch_admission",
            "proof_admitted": True,
            "feature_proof_admitted": True,
            "expected_freshness_anchor_digest_bound": True,
            "external_freshness_proven": True,
            "full_runtime_dispatch_runner_proven": True,
            "full_runtime_dispatch_proven": False,
            "custom_codex_flow_proven": True,
            "api_lane_called": True,
            "dispatch_proven": True,
            "codex_working_flow_delivery_proven": True,
            "custom_codex_ui_visibility_proven": True,
            "product_ready": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "native_codex_subagent_used_as_dip": False,
            "codex_native_subagent_used_as_dip": False,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "natural_phrase_recorded": False,
            "raw_dom_exposed": False,
            "raw_ax_tree_exposed": False,
            "raw_jsonl_recorded": False,
            "tool_call_arguments_recorded": False,
            "route_candidate_recorded": False,
            "raw_route_id_recorded": False,
            "selected_api_route_id_recorded": False,
            "raw_provider_response_recorded": False,
            "provider_response_text_recorded": False,
            "provider_response_preview_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_freshness_anchor_recorded": False,
            "proof_dir_path_recorded": False,
            "artifact_file_paths_recorded": False,
            "state_written": False,
            "runtime_effective_truth_written": False,
            "evidence_written": False,
            "file_mutation_attempted": False,
            "blocking_reasons": [],
        }

        packet = seal.build_full_runtime_dispatch_admission_seal_packet(
            proof_dir="proof",
            expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            admission_packet=admission_packet,
            admission_failures=seal._admission_failures(admission_packet),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertFalse(packet["feature_runtime_proof_sealed"])
        self.assertIn(
            "admission_full_runtime_dispatch_proven_not_true",
            packet["blocking_reasons"],
        )

    def test_unsafe_admission_claim_blocks_as_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            unsafe_admission = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            unsafe_admission["product_ready"] = True

            with mock.patch(
                "wild_boar_proxy.full_runtime_dispatch_admission_seal."
                "run_full_runtime_dispatch_admission_command",
                return_value=unsafe_admission,
            ):
                packet = _seal(
                    proof_dir,
                    expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertFalse(packet["product_ready"])
        self.assertIn(
            "admission_product_ready_unsafe",
            packet["blocking_reasons"],
        )

    def test_admission_packet_secret_leak_blocks_as_unsafe(self) -> None:
        admission_packet = {
            "status": "ok",
            "machine_error_code": "OK",
            "effect": "read",
            "packet_kind": "wbp_full_runtime_dispatch_admission",
            "proof_admitted": True,
            "feature_proof_admitted": True,
            "expected_freshness_anchor_digest_bound": True,
            "external_freshness_proven": True,
            "full_runtime_dispatch_runner_proven": True,
            "full_runtime_dispatch_proven": True,
            "custom_codex_flow_proven": True,
            "api_lane_called": True,
            "dispatch_proven": True,
            "codex_working_flow_delivery_proven": True,
            "custom_codex_ui_visibility_proven": True,
            "product_ready": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "native_codex_subagent_used_as_dip": False,
            "codex_native_subagent_used_as_dip": False,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "natural_phrase_recorded": False,
            "raw_dom_exposed": False,
            "raw_ax_tree_exposed": False,
            "raw_jsonl_recorded": False,
            "tool_call_arguments_recorded": False,
            "route_candidate_recorded": False,
            "raw_route_id_recorded": False,
            "selected_api_route_id_recorded": False,
            "raw_provider_response_recorded": False,
            "provider_response_text_recorded": False,
            "provider_response_preview_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "raw_freshness_anchor_recorded": False,
            "proof_dir_path_recorded": False,
            "artifact_file_paths_recorded": False,
            "state_written": False,
            "runtime_effective_truth_written": False,
            "evidence_written": False,
            "file_mutation_attempted": False,
            "blocking_reasons": [],
            "leaked_path": "/private/tmp/wbp-proof-secret",
        }

        with mock.patch(
            "wild_boar_proxy.full_runtime_dispatch_admission_seal."
            "run_full_runtime_dispatch_admission_command",
            return_value=admission_packet,
        ):
            packet = seal.run_full_runtime_dispatch_admission_seal_command(
                proof_dir="/private/tmp/wbp-proof-secret",
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            seal.FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["proof_admission_sealed"])
        self.assertIn(
            "admission_packet_semantic_violation",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "admission_packet_secret_material_present",
            packet["blocking_reasons"],
        )

    def test_cli_parses_seal_as_read_and_dispatches(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "full-runtime-dispatch-admission-seal",
                "--proof-dir",
                "proof",
                "--expected-freshness-anchor-digest",
                FRESHNESS_ANCHOR_DIGEST,
                "--json",
            ]
        )
        self.assertEqual(
            args.router_hook_command,
            "full-runtime-dispatch-admission-seal",
        )
        self.assertEqual(cli_mod.command_effect_from_args(args), "read")
        self.assertEqual(args.expected_freshness_anchor_digest, FRESHNESS_ANCHOR_DIGEST)

        expected = seal.build_full_runtime_dispatch_admission_seal_packet(
            proof_dir="proof",
            expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            input_failures=["expected_freshness_anchor_digest_missing"],
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_full_runtime_dispatch_admission_seal_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "full-runtime-dispatch-admission-seal",
                    "--proof-dir",
                    "proof",
                    "--expected-freshness-anchor-digest",
                    FRESHNESS_ANCHOR_DIGEST,
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        self.assertEqual(payload["effect"], "read")
        run_command.assert_called_once_with(
            proof_dir="proof",
            expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
        )


if __name__ == "__main__":
    unittest.main()
