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
from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import custom_codex_ui_visibility_proof as ui_visibility
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
    _events_for_packet,
    _file_metadata as _working_flow_file_metadata,
    _integrated_packet,
    _jsonl_from_events,
)
from test_custom_codex_ui_visibility_proof import (  # noqa: E402
    _file_metadata as _ui_file_metadata,
    _native_packet,
    _source_packet,
)


REQUEST_ID = "wbp-full-runtime-runner-001"


def _secret_values() -> list[str]:
    return [PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )


def _ui_packet_for_handoff(
    handoff_digest: str,
    *,
    source_overrides: dict[str, object] | None = None,
    native_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    expected_visible_text = f"WBP_FULL_RUNTIME_RUNNER_VISIBLE_{handoff_digest}_{REQUEST_ID}"
    source = _source_packet(
        {
            "handoff_payload_digest": handoff_digest,
            "visible_source_marker_digest": handoff_digest,
            **(source_overrides or {}),
        }
    )
    native = _native_packet(
        expected_text=expected_visible_text,
        request_id=REQUEST_ID,
        overrides=native_overrides,
    )
    packet = ui_visibility.build_custom_codex_ui_visibility_proof_packet(
        source,
        native,
        expected_visible_text=expected_visible_text,
        request_id=REQUEST_ID,
        file_metadata=_ui_file_metadata(),
    )
    assert packet["status"] == "ok"
    return packet


def _write_fixture(
    root: Path,
    *,
    source_overrides: dict[str, object] | None = None,
    ui_packet: dict[str, object] | None = None,
) -> dict[str, Path | dict[str, object]]:
    source = {**_integrated_packet(), **(source_overrides or {})}
    events = _events_for_packet(source)
    working_flow_packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata=_working_flow_file_metadata(),
        secret_values=_secret_values(),
    )
    assert working_flow_packet["status"] == "ok"
    ui = (
        _ui_packet_for_handoff(str(working_flow_packet["handoff_payload_digest"]))
        if ui_packet is None
        else ui_packet
    )

    real_hook_file = root / "real-custom-hook-proof.json"
    working_flow_file = root / "working-flow-delivery-proof.json"
    jsonl_file = root / "codex-exec.jsonl"
    ui_file = root / "custom-codex-ui-visibility-proof.json"
    _write_json(real_hook_file, source)
    _write_json(working_flow_file, working_flow_packet)
    jsonl_file.write_text(_jsonl_from_events(events), encoding="utf-8")
    _write_json(ui_file, ui)
    return {
        "real_hook_file": real_hook_file,
        "working_flow_file": working_flow_file,
        "jsonl_file": jsonl_file,
        "ui_file": ui_file,
        "source": source,
        "working_flow_packet": working_flow_packet,
        "ui_packet": ui,
    }


def _run_fixture(root: Path, fixture: dict[str, Path | dict[str, object]]) -> dict[str, object]:
    return runner.run_full_runtime_dispatch_proof_runner_command(
        real_custom_hook_proof_file=str(fixture["real_hook_file"]),
        working_flow_delivery_proof_file=str(fixture["working_flow_file"]),
        codex_exec_jsonl_file=str(fixture["jsonl_file"]),
        custom_codex_ui_visibility_proof_file=str(fixture["ui_file"]),
        proof_dir=str(root / "proof"),
    )


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in _secret_values():
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class FullRuntimeDispatchProofRunnerTests(unittest.TestCase):
    def test_positive_replays_full_runtime_chain_from_file_backed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)

            packet = _run_fixture(root, fixture)
            proof_dir = root / "proof"
            manifest = json.loads(
                (
                    proof_dir
                    / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
                ).read_text(encoding="utf-8")
            )
            persisted_runner = json.loads(
                (
                    proof_dir / runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
                ).read_text(encoding="utf-8")
            )
            final_packet = json.loads(
                (proof_dir / "full-runtime-dispatch-proof.packet.json").read_text(
                    encoding="utf-8"
                )
            )
            written_json_artifacts = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in proof_dir.glob("*.json")
            }

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_PACKET_KIND,
        )
        self.assertEqual(packet, persisted_runner)
        self.assertEqual(
            manifest["packet_kind"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_PACKET_KIND,
        )
        self.assertFalse(manifest["input_file_paths_recorded"])
        self.assertFalse(manifest["artifact_file_paths_recorded"])
        self.assertTrue(packet["runner_inputs_valid"])
        self.assertTrue(packet["full_runtime_dispatch_runner_proven"])
        self.assertTrue(packet["full_runtime_dispatch_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packet["handoff_payload_digest"], final_packet["handoff_payload_digest"])
        self.assertTrue(packet["manifest_file_written"])
        self.assertTrue(packet["runner_packet_file_written"])
        self.assertFalse(packet["manifest_file_path_recorded"])
        self.assertFalse(packet["runner_packet_file_path_recorded"])
        self.assertFalse(packet["proof_dir_path_recorded"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["evidence_written"])
        self.assertTrue(packet["file_mutation_attempted"])
        self.assertFalse(packet["state_written"])
        self.assertFalse(packet["runtime_effective_truth_written"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertIn("full-runtime-dispatch-proof.packet.json", packet["artifact_file_names"])
        self.assertTrue(
            all(entry["file_path_recorded"] is False for entry in packet["artifact_summaries"])
        )
        self.assertTrue(
            all(entry["file_path_recorded"] is False for entry in manifest["input_files"])
        )
        for artifact_name, artifact_packet in written_json_artifacts.items():
            serialized = json.dumps(artifact_packet, ensure_ascii=False, sort_keys=True)
            for forbidden in _secret_values():
                self.assertNotIn(forbidden, serialized, artifact_name)
                self.assertFalse(packet_contains_text(artifact_packet, forbidden))
            self.assertNotIn(str(root), serialized)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_proof_dir_does_not_claim_evidence_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)

            packet = runner.run_full_runtime_dispatch_proof_runner_command(
                real_custom_hook_proof_file=str(fixture["real_hook_file"]),
                working_flow_delivery_proof_file=str(fixture["working_flow_file"]),
                codex_exec_jsonl_file=str(fixture["jsonl_file"]),
                custom_codex_ui_visibility_proof_file=str(fixture["ui_file"]),
                proof_dir="",
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertIn("proof_dir_missing", packet["blocking_reasons"])
        self.assertFalse(packet["manifest_file_written"])
        self.assertFalse(packet["runner_packet_file_written"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        self.assertEqual(packet["artifact_file_names"], [])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_write_failure_does_not_claim_evidence_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)

            with mock.patch(
                "wild_boar_proxy.full_runtime_dispatch_proof_runner.write_json_atomic",
                side_effect=OSError("blocked"),
            ):
                packet = _run_fixture(root, fixture)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_ARTIFACT_WRITE_FAILED,
        )
        self.assertIn("full_runtime_runner_artifact_write_failed", packet["blocking_reasons"])
        self.assertIn("runner_manifest_write_failed", packet["blocking_reasons"])
        self.assertIn("runner_packet_write_failed", packet["blocking_reasons"])
        self.assertFalse(packet["manifest_file_written"])
        self.assertFalse(packet["runner_packet_file_written"])
        self.assertFalse(packet["evidence_written"])
        self.assertFalse(packet["file_mutation_attempted"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_blocks_missing_jsonl_without_claiming_full_runtime_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)
            Path(fixture["jsonl_file"]).unlink()

            packet = _run_fixture(root, fixture)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_INPUT_INVALID,
        )
        self.assertFalse(packet["runner_inputs_valid"])
        self.assertFalse(packet["full_runtime_dispatch_runner_proven"])
        self.assertFalse(packet["full_runtime_dispatch_proven"])
        self.assertIn("codex_exec_jsonl_file_missing", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_blocks_ui_handoff_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            base_fixture = _write_fixture(root)
            bad_ui = _ui_packet_for_handoff("c" * 64)
            fixture = _write_fixture(root, ui_packet=bad_ui)
            self.assertNotEqual(
                base_fixture["working_flow_packet"]["handoff_payload_digest"],
                bad_ui["handoff_payload_digest"],
            )

            packet = _run_fixture(root, fixture)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_runner_proven"])
        self.assertIn("handoff_payload_digest_mismatch", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_blocks_malformed_ui_candidate_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)
            ui_packet = dict(fixture["ui_packet"])
            ui_packet["custom_response_like_candidate_count"] = "1"
            _write_json(Path(fixture["ui_file"]), ui_packet)

            packet = _run_fixture(root, fixture)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_runner_proven"])
        self.assertIn(
            "ui_visibility_like_candidate_count_missing",
            packet["blocking_reasons"],
        )
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_blocks_unproven_api_dispatch_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = _write_fixture(root)
            source = dict(fixture["source"])
            source["api_lane_called"] = False
            _write_json(Path(fixture["real_hook_file"]), source)

            packet = _run_fixture(root, fixture)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            runner.FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID,
        )
        self.assertFalse(packet["full_runtime_dispatch_runner_proven"])
        self.assertIn("official_e2e_api_lane_called_not_true", packet["blocking_reasons"])
        _assert_no_raw_prompt_route_or_provider(self, packet)

    def test_cli_parses_runner_as_mutate_and_dispatches(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "full-runtime-dispatch-proof-runner",
                "--real-custom-hook-proof-file",
                "hook.json",
                "--working-flow-delivery-proof-file",
                "working-flow.json",
                "--codex-exec-jsonl-file",
                "codex.jsonl",
                "--custom-codex-ui-visibility-proof-file",
                "ui.json",
                "--proof-dir",
                "proof",
                "--json",
            ]
        )
        self.assertEqual(args.router_hook_command, "full-runtime-dispatch-proof-runner")
        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")

        expected = runner.build_full_runtime_dispatch_proof_runner_packet(
            input_metadata={"proof_dir_present": True, "proof_dir_path_recorded": False},
            artifact_summaries=[],
            final_packet={},
            manifest_packet={},
        )
        stdout = io.StringIO()
        with (
            mock.patch(
                "wild_boar_proxy.cli.run_full_runtime_dispatch_proof_runner_command",
                return_value=expected,
            ) as run_command,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = cli_mod.main(
                [
                    "router-hook",
                    "full-runtime-dispatch-proof-runner",
                    "--real-custom-hook-proof-file",
                    "hook.json",
                    "--working-flow-delivery-proof-file",
                    "working-flow.json",
                    "--codex-exec-jsonl-file",
                    "codex.jsonl",
                    "--custom-codex-ui-visibility-proof-file",
                    "ui.json",
                    "--proof-dir",
                    "proof",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, payload["exit_code"])
        run_command.assert_called_once_with(
            real_custom_hook_proof_file="hook.json",
            working_flow_delivery_proof_file="working-flow.json",
            codex_exec_jsonl_file="codex.jsonl",
            custom_codex_ui_visibility_proof_file="ui.json",
            proof_dir="proof",
        )


if __name__ == "__main__":
    unittest.main()
