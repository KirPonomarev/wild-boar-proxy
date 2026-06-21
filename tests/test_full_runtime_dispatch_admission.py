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
from wild_boar_proxy import full_runtime_dispatch_admission as admission
from wild_boar_proxy import full_runtime_dispatch_proof_runner as runner
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_codex_working_flow_delivery_proof import (  # noqa: E402
    EXPECTED_TEXT,
    PROMPT,
    RAW_PROVIDER_TEXT,
    ROUTE_ID,
)
from test_full_runtime_dispatch_proof_runner import (  # noqa: E402
    _run_fixture,
    _write_fixture,
)


FRESHNESS_ANCHOR_DIGEST = "a" * 64
OTHER_FRESHNESS_ANCHOR_DIGEST = "b" * 64


def _secret_values() -> list[str]:
    return [PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT]


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )


def _write_valid_proof(
    root: Path,
    *,
    source_overrides: dict[str, object] | None = None,
    freshness_anchor_digest: str | None = None,
) -> tuple[Path, dict[str, object]]:
    root.mkdir(parents=True, exist_ok=True)
    fixture = _write_fixture(root, source_overrides=source_overrides)
    packet = _run_fixture(
        root,
        fixture,
        freshness_anchor_digest=freshness_anchor_digest,
    )
    assert packet["status"] == "ok"
    return root / "proof", packet


def _admit(
    proof_dir: Path,
    *,
    expected_freshness_anchor_digest: str | None = None,
) -> dict[str, object]:
    return admission.run_full_runtime_dispatch_admission_command(
        proof_dir=str(proof_dir),
        expected_freshness_anchor_digest=expected_freshness_anchor_digest,
    )


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    root: Path | None = None,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in _secret_values():
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    if root is not None:
        testcase.assertNotIn(str(root), serialized)
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


class FullRuntimeDispatchAdmissionTests(unittest.TestCase):
    def test_positive_admits_coherent_file_backed_proof_dir_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir, runner_packet = _write_valid_proof(root)
            before = {path.name: path.stat().st_mtime_ns for path in proof_dir.glob("*.json")}

            packet = _admit(proof_dir)
            after = {path.name: path.stat().st_mtime_ns for path in proof_dir.glob("*.json")}

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "read")
        self.assertEqual(
            packet["packet_kind"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_PACKET_KIND,
        )
        self.assertTrue(packet["proof_admitted"])
        self.assertTrue(packet["feature_proof_admitted"])
        self.assertTrue(packet["fresh_session_bound"])
        self.assertTrue(packet["artifact_set_coherent"])
        self.assertFalse(packet["freshness_anchor_required"])
        self.assertFalse(packet["expected_freshness_anchor_digest_present"])
        self.assertEqual(packet["expected_freshness_anchor_digest"], "")
        self.assertFalse(packet["expected_freshness_anchor_digest_bound"])
        self.assertFalse(packet["freshness_anchor_digest_present"])
        self.assertEqual(packet["freshness_anchor_digest"], "")
        self.assertFalse(packet["freshness_anchor_bound_to_runner"])
        self.assertFalse(packet["freshness_anchor_bound_to_manifest"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertFalse(packet["raw_freshness_anchor_recorded"])
        self.assertTrue(packet["runner_packet_present"])
        self.assertTrue(packet["manifest_present"])
        self.assertTrue(packet["final_full_runtime_packet_present"])
        self.assertTrue(packet["full_runtime_dispatch_runner_proven"])
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packet["handoff_payload_digest"], runner_packet["handoff_payload_digest"])
        self.assertEqual(packet["artifact_count"], 8)
        self.assertIn("full-runtime-dispatch-proof.packet.json", packet["artifact_file_names"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["changed_files"], [])
        self.assertFalse(packet["proof_dir_path_recorded"])
        self.assertFalse(packet["artifact_file_paths_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["runtime_effective_truth_written"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertEqual(before, after)
        _assert_no_raw_prompt_route_or_provider(self, packet, root)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_expected_freshness_anchor_digest_admits_matching_proof_dir(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof_dir, runner_packet = _write_valid_proof(
                root,
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["proof_admitted"])
        self.assertTrue(packet["freshness_anchor_required"])
        self.assertTrue(packet["expected_freshness_anchor_digest_present"])
        self.assertEqual(
            packet["expected_freshness_anchor_digest"],
            FRESHNESS_ANCHOR_DIGEST,
        )
        self.assertTrue(packet["expected_freshness_anchor_digest_bound"])
        self.assertTrue(packet["freshness_anchor_digest_present"])
        self.assertEqual(packet["freshness_anchor_digest"], FRESHNESS_ANCHOR_DIGEST)
        self.assertTrue(packet["freshness_anchor_bound_to_runner"])
        self.assertTrue(packet["freshness_anchor_bound_to_manifest"])
        self.assertTrue(packet["external_freshness_proven"])
        self.assertFalse(packet["raw_freshness_anchor_recorded"])
        self.assertEqual(packet["handoff_payload_digest"], runner_packet["handoff_payload_digest"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        _assert_no_raw_prompt_route_or_provider(self, packet, root)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_expected_freshness_anchor_digest_blocks_old_non_fresh_proof_dir(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertTrue(packet["freshness_anchor_required"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn(
            "runner_freshness_anchor_digest_missing",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "manifest_freshness_anchor_digest_missing",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_wrong_expected_freshness_anchor_digest_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=OTHER_FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn(
            "runner_freshness_anchor_digest_mismatch",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "manifest_freshness_anchor_digest_mismatch",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_invalid_expected_freshness_anchor_digest_blocks_as_input_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest="not-a-digest",
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn(
            "expected_freshness_anchor_digest_invalid",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_runner_freshness_anchor_digest_tamper_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["freshness_anchor_digest"] = OTHER_FRESHNESS_ANCHOR_DIGEST
            _write_json(runner_path, runner_payload)

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn("runner_freshness_anchor_digest_mismatch", packet["blocking_reasons"])
        self.assertIn("freshness_anchor_digest_runner_manifest_mismatch", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_manifest_freshness_anchor_digest_tamper_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            manifest_path = (
                proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
            )
            manifest_payload = _read_json(manifest_path)
            manifest_payload["freshness_anchor_digest"] = OTHER_FRESHNESS_ANCHOR_DIGEST
            _write_json(manifest_path, manifest_payload)

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn("manifest_file_sha256_mismatch", packet["blocking_reasons"])
        self.assertIn("manifest_freshness_anchor_digest_mismatch", packet["blocking_reasons"])
        self.assertIn("freshness_anchor_digest_runner_manifest_mismatch", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_missing_manifest_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            (proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME).unlink()

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn("manifest_file_missing", packet["blocking_reasons"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_corrupted_manifest_json_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            (
                proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
            ).write_text("{not-json", encoding="utf-8")

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn("manifest_file_json_invalid", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_manifest_hash_mismatch_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            manifest_path = (
                proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
            )
            manifest = _read_json(manifest_path)
            manifest["runner_status"] = "error"
            _write_json(manifest_path, manifest)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn("manifest_file_sha256_mismatch", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_runner_manifest_packet_kind_mismatch_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["manifest_packet_kind"] = "wrong_manifest_kind"
            _write_json(runner_path, runner_payload)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "runner_manifest_packet_kind_mismatch",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_runner_artifact_file_names_summary_mismatch_blocks_admission(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["artifact_file_names"] = []
            _write_json(runner_path, runner_payload)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "runner_artifact_file_names_invalid",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "runner_artifact_file_names_summary_mismatch",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_post_write_artifact_substitution_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_dir, _first_runner = _write_valid_proof(root / "first")
            target = first_dir / "full-runtime-dispatch-proof.packet.json"
            substituted = _read_json(target)
            substituted["post_write_tamper_marker"] = "different_artifact_bytes"
            _write_json(target, substituted)

            packet = _admit(first_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "full-runtime-dispatch-proof.packet.json_runner_file_sha256_mismatch",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_unproven_runner_packet_blocks_without_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["full_runtime_dispatch_runner_proven"] = False
            _write_json(runner_path, runner_payload)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_NOT_PROVEN,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "runner_full_runtime_dispatch_runner_proven_not_true",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_product_ready_tamper_blocks_as_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["product_ready"] = True
            _write_json(runner_path, runner_payload)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "full_runtime_dispatch_proof_runner_product_ready_unsafe",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_raw_freshness_anchor_recorded_tamper_blocks_as_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(
                Path(temp_dir),
                freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )
            runner_path = proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
            runner_payload = _read_json(runner_path)
            runner_payload["raw_freshness_anchor_recorded"] = True
            _write_json(runner_path, runner_payload)

            packet = _admit(
                proof_dir,
                expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertFalse(packet["external_freshness_proven"])
        self.assertIn(
            "full_runtime_dispatch_proof_runner_raw_freshness_anchor_recorded_unsafe",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["raw_freshness_anchor_recorded"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_raw_route_or_provider_leak_tamper_blocks_as_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            final_path = proof_dir / "full-runtime-dispatch-proof.packet.json"
            final_payload = _read_json(final_path)
            final_payload["raw_route_id_recorded"] = True
            final_payload["provider_response_text_recorded"] = True
            _write_json(final_path, final_payload)

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "full_runtime_dispatch_proof_raw_route_id_recorded_unsafe",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "full_runtime_dispatch_proof_provider_response_text_recorded_unsafe",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_missing_artifact_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proof_dir, _runner_packet = _write_valid_proof(Path(temp_dir))
            (proof_dir / "official-delivery-candidate-join.packet.json").unlink()

            packet = _admit(proof_dir)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
        )
        self.assertFalse(packet["proof_admitted"])
        self.assertIn(
            "official-delivery-candidate-join.packet.json_artifact_file_missing",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_cli_parses_admission_as_read_and_dispatches(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "full-runtime-dispatch-admission",
                "--proof-dir",
                "proof",
                "--expected-freshness-anchor-digest",
                FRESHNESS_ANCHOR_DIGEST,
                "--json",
            ]
        )
        self.assertEqual(args.router_hook_command, "full-runtime-dispatch-admission")
        self.assertEqual(cli_mod.command_effect_from_args(args), "read")
        self.assertEqual(args.expected_freshness_anchor_digest, FRESHNESS_ANCHOR_DIGEST)

        expected = admission.build_full_runtime_dispatch_admission_packet(
            proof_dir="proof",
            expected_freshness_anchor_digest=FRESHNESS_ANCHOR_DIGEST,
            metadata={"proof_dir_present": False, "proof_dir_path_recorded": False},
            runner_packet={},
            manifest_packet={},
            final_packet={},
            artifact_packets={},
            input_failures=["proof_dir_missing"],
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_full_runtime_dispatch_admission_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "full-runtime-dispatch-admission",
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
