# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_custom_codex_hook_proof as hook_proof
from wild_boar_proxy import real_user_prompt_submit_ledger_proof as ledger_proof
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_user_prompt_submit_hook_producer import (  # noqa: E402
    PROMPT,
    ROOT,
    ROUTE_ID,
    TEST_CODEX_CURRENT_HASH,
    _env_with_fake_codex_app_server,
    _event,
    _paths,
    _write_context,
)


def _env(paths) -> dict[str, str]:
    return _env_with_fake_codex_app_server(paths)


def _write_codex_trust_state(paths) -> None:
    trust_key = producer.hook_trust_key_for_paths(paths)
    with paths.config_toml.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[hooks.state."
            + json.dumps(trust_key)
            + "]\ntrusted_hash = "
            + json.dumps(TEST_CODEX_CURRENT_HASH)
            + "\n"
        )


def _run_hook(
    paths,
    *,
    hook_hash: str,
    origin_state: str = hook_proof.ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    use_event_file: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "wild_boar_proxy.user_prompt_submit_hook_producer",
        "run-hook",
        "--ledger-file",
        str(producer.hook_ledger_path(paths)),
        "--trusted-hook-config-sha256",
        hook_hash,
        "--loaded-hook-config-sha256",
        hook_hash,
        "--origin-state",
        origin_state,
        "--json",
    ]
    input_text = json.dumps(_event(), sort_keys=True)
    if use_event_file:
        event_path = paths.profile_dir / "event-file-input.json"
        event_path.write_text(input_text + "\n", encoding="utf-8")
        command.extend(["--event-file", str(event_path)])
        input_text = None
    return subprocess.run(
        command,
        cwd=ROOT,
        env=_env(paths),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_ledger_proof(paths) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "user-prompt-submit-ledger-proof",
            "--prompt",
            PROMPT,
            "--json",
        ],
        cwd=ROOT,
        env=_env(paths),
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_no_prompt_route_or_secret(
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
    testcase.assertFalse(packet["secret_value_exposed"])


class RealUserPromptSubmitLedgerProofTests(unittest.TestCase):
    def test_readiness_observes_codex_trust_state_without_dispatch_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            _write_codex_trust_state(paths)

            packet = producer.build_user_prompt_submit_readiness_packet(
                paths=paths,
                codex_hook_current_hash=TEST_CODEX_CURRENT_HASH,
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["hook_config_present"])
        self.assertTrue(packet["hook_enabled"])
        self.assertTrue(packet["hook_command_path_resolves"])
        self.assertTrue(packet["hook_script_executable"])
        self.assertTrue(packet["hook_config_digest_bound"])
        self.assertTrue(packet["codex_hook_trust_state_present"])
        self.assertTrue(packet["codex_hook_trust_state_matches_hook_slot"])
        self.assertTrue(packet["codex_hook_trusted_hash_present"])
        self.assertTrue(packet["codex_hook_trusted_hash_valid"])
        self.assertFalse(packet["codex_hook_trusted_hash_matches_hook_definition"])
        self.assertTrue(packet["codex_hook_trusted_hash_matches_current_hash"])
        self.assertTrue(packet["codex_hook_trusted_by_profile_state"])
        self.assertTrue(packet["hook_trusted"])
        self.assertFalse(packet["hook_requires_manual_review"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_stdin_hook_event_proves_real_ledger_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )
            _write_codex_trust_state(paths)
            hook_hash = str(install["hook_definition_digest"])
            run_result = _run_hook(paths, hook_hash=hook_hash)
            proof_result = _run_ledger_proof(paths)

        self.assertEqual(run_result.returncode, 0, run_result.stderr)
        run_packet = json.loads(run_result.stdout)
        self.assertEqual(run_packet["hook_event_transport"], "stdin")
        self.assertTrue(run_packet["hook_event_transport_stdin"])

        self.assertEqual(proof_result.returncode, 0, proof_result.stderr)
        packet = json.loads(proof_result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["packet_kind"],
            ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        )
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["hook_readiness_ok"])
        self.assertTrue(packet["hook_ledger_file_profile_owned"])
        self.assertTrue(packet["hook_producer_ledger_proven"])
        self.assertTrue(packet["hook_event_transport_stdin"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_written"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["custom_codex_origin_proven"])
        self.assertTrue(packet["native_router_hook_observed"])
        self.assertFalse(packet["source_file_unforgeable"])
        self.assertFalse(packet["cryptographic_origin_proven"])
        self.assertTrue(packet["does_not_prove_source_file_unforgeable"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertEqual(packet["dispatch_status"], "not_attempted")
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["handoff_file_written"])
        self.assertFalse(packet["handoff_delivered"])
        self.assertFalse(packet["delivery_observed"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_prompt_route_or_secret(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_event_file_manual_transport_cannot_claim_real_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )
            _write_codex_trust_state(paths)
            hook_hash = str(install["hook_definition_digest"])
            run_result = _run_hook(paths, hook_hash=hook_hash, use_event_file=True)
            proof_result = _run_ledger_proof(paths)

        self.assertEqual(run_result.returncode, 0, run_result.stderr)
        run_packet = json.loads(run_result.stdout)
        self.assertEqual(run_packet["hook_event_transport"], "event_file")
        packet = json.loads(proof_result.stdout)
        self.assertEqual(proof_result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_TRANSPORT_NOT_HOOK_STDIN,
        )
        self.assertFalse(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn("hook_event_transport_not_stdin", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_synthetic_origin_cannot_claim_real_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )
            _write_codex_trust_state(paths)
            hook_hash = str(install["hook_definition_digest"])
            _run_hook(
                paths,
                hook_hash=hook_hash,
                origin_state=hook_proof.ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
            )
            proof_result = _run_ledger_proof(paths)

        packet = json.loads(proof_result.stdout)
        self.assertEqual(proof_result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            hook_proof.USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX,
        )
        self.assertFalse(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_codex_flow_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn(
            "origin_state_not_custom_codex_flow_proven",
            packet["blocking_reasons"],
        )
        _assert_no_prompt_route_or_secret(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_missing_codex_trust_state_blocks_before_real_ledger_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )
            hook_hash = str(install["hook_definition_digest"])
            _run_hook(paths, hook_hash=hook_hash)
            proof_result = _run_ledger_proof(paths)

        packet = json.loads(proof_result.stdout)
        self.assertEqual(proof_result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_READINESS_NOT_TRUSTED,
        )
        self.assertFalse(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertIn("hook_readiness_packet_not_ok", packet["blocking_reasons"])
        self.assertIn("codex_hook_trust_state_not_proven", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        _assert_no_prompt_route_or_secret(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_ledger_overclaim_blocks_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )
            _write_codex_trust_state(paths)
            hook_hash = str(install["hook_definition_digest"])
            _run_hook(paths, hook_hash=hook_hash)
            ledger_path = producer.hook_ledger_path(paths)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["product_ready"] = True
            ledger_path.write_text(json.dumps(ledger) + "\n", encoding="utf-8")
            proof_result = _run_ledger_proof(paths)

        packet = json.loads(proof_result.stdout)
        self.assertEqual(proof_result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            hook_proof.USER_PROMPT_SUBMIT_UNSAFE_CLAIM,
        )
        self.assertFalse(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_ledger_proof_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "user-prompt-submit-ledger-proof",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
