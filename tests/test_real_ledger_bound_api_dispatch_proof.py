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
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_ledger_bound_api_dispatch_proof as proof
from wild_boar_proxy import real_user_prompt_submit_ledger_proof as ledger_proof
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_user_prompt_submit_hook_producer import (  # noqa: E402
    ROOT,
    ROUTE_ID,
    TEST_CODEX_CURRENT_HASH,
    _env_with_fake_codex_app_server,
    _event,
    _paths,
    _runtime_context,
)


PROMPT = "Codex, дай задачу DIP: докажи ledger-bound API dispatch."
OTHER_PROMPT = "Codex, дай задачу DIP: другой prompt."
RAW_PROVIDER_TEXT = "raw provider text must not be stored"


def _env(paths) -> dict[str, str]:
    return _env_with_fake_codex_app_server(paths)


def _write_context(paths, context: dict[str, object]) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    (paths.profile_dir / "wbp-agent-runtime-context.json").write_text(
        json.dumps(context) + "\n",
        encoding="utf-8",
    )


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
    prompt: str = PROMPT,
    origin_state: str = "custom_codex_flow_proven",
    use_event_file: bool = False,
) -> subprocess.CompletedProcess[str]:
    install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
    _write_codex_trust_state(paths)
    command = [
        sys.executable,
        "-m",
        "wild_boar_proxy.user_prompt_submit_hook_producer",
        "run-hook",
        "--ledger-file",
        str(producer.hook_ledger_path(paths)),
        "--trusted-hook-config-sha256",
        str(install["hook_definition_digest"]),
        "--loaded-hook-config-sha256",
        str(install["hook_definition_digest"]),
        "--origin-state",
        origin_state,
        "--json",
    ]
    input_text = json.dumps(_event(prompt=prompt), sort_keys=True)
    if use_event_file:
        event_file = paths.profile_dir / "manual-event.json"
        event_file.write_text(input_text + "\n", encoding="utf-8")
        command.extend(["--event-file", str(event_file)])
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


def _prepare_paths(
    root: Path,
    *,
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    origin_state: str = "custom_codex_flow_proven",
    use_event_file: bool = False,
):
    paths = _paths(root)
    _write_context(paths, _runtime_context() if context is None else context)
    run_result = _run_hook(
        paths,
        prompt=prompt,
        origin_state=origin_state,
        use_event_file=use_event_file,
    )
    if run_result.returncode != 0:
        raise AssertionError(run_result.stderr)
    return paths


def _run_dispatch_proof(
    paths,
    *,
    prompt: str = PROMPT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "ledger-bound-dispatch-proof",
            "--prompt",
            prompt,
            "--json",
        ],
        cwd=ROOT,
        env=_env(paths),
        text=True,
        capture_output=True,
        check=False,
    )


def _ledger_proof_packet(paths, *, prompt: str = PROMPT) -> dict[str, object]:
    with mock.patch.dict(
        os.environ,
        _env(paths),
    ):
        return ledger_proof.run_real_user_prompt_submit_ledger_proof_command(
            paths=paths,
            prompt_text=prompt,
        )


def _dispatch_packet(
    *,
    ledger_packet: dict[str, object],
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
) -> dict[str, object]:
    return proof.build_real_ledger_bound_api_dispatch_proof_packet(
        ledger_proof_packet=ledger_packet,
        prompt_text=prompt,
        runtime_context=_runtime_context() if context is None else context,
        api_lane_adapter_available=api_lane_adapter_available,
        controlled_provider_available=controlled_provider_available,
        controlled_provider_error_code=controlled_provider_error_code,
        secret_values=[PROMPT, OTHER_PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT],
    )


def _assert_no_raw_prompt_route_or_provider(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    prompts: list[str] | None = None,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertNotIn(RAW_PROVIDER_TEXT, serialized)
    for prompt in prompts or [PROMPT]:
        testcase.assertNotIn(prompt, serialized)
        testcase.assertFalse(packet_contains_text(packet, prompt))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


def _assert_no_handoff_ui_or_product_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["live_provider_proven"])
    testcase.assertFalse(packet["live_provider_response_proven"])
    testcase.assertFalse(packet["external_live_provider_response_proven"])
    testcase.assertEqual(packet["live_provider_status"], "not_attempted")
    testcase.assertFalse(packet["handoff_file_written"])
    testcase.assertFalse(packet["handoff_delivered"])
    testcase.assertFalse(packet["delivery_observed"])
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["codex_working_flow_delivery_proven"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["native_free_chat_router_product_ready"])
    testcase.assertFalse(packet["native_free_chat_router_delivery_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_live_provider"])
    testcase.assertTrue(packet["does_not_prove_handoff"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


class RealLedgerBoundApiDispatchProofTests(unittest.TestCase):
    def test_positive_cli_proves_real_ledger_bound_api_dispatch_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir))
            result = _run_dispatch_proof(paths)

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.REAL_LEDGER_BOUND_API_DISPATCH_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertTrue(packet["custom_codex_origin_proven"])
        self.assertTrue(packet["native_router_hook_observed"])
        self.assertTrue(packet["user_prompt_submit_hook_observed"])
        self.assertEqual(packet["hook_event_transport"], "stdin")
        self.assertTrue(packet["hook_event_transport_stdin"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["prompt_digest_bound_to_ledger"])
        self.assertTrue(packet["prompt_digest_bound_to_dispatch"])
        self.assertTrue(packet["ledger_bound_dispatch_admitted"])
        self.assertTrue(packet["alias_context_read"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertEqual(packet["selected_slot"], "dip")
        self.assertTrue(packet["allowed_route_enforced"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_adapter_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_lane_provider_called"])
        self.assertTrue(packet["api_response_received"])
        self.assertTrue(packet["response_digest_bound"])
        self.assertTrue(packet["provider_response_digest"])
        self.assertTrue(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertEqual(packet["dispatch_status"], "proven")
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_digest_mismatch_blocks_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir), prompt=PROMPT)
            ledger_packet = _ledger_proof_packet(paths, prompt=PROMPT)
            packet = _dispatch_packet(
                ledger_packet=ledger_packet,
                prompt=OTHER_PROMPT,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_LEDGER_BOUND_API_DISPATCH_DIGEST_MISMATCH,
        )
        self.assertIn("prompt_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["prompt_digest_bound_to_ledger"])
        self.assertFalse(packet["ledger_bound_dispatch_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet, prompts=[PROMPT, OTHER_PROMPT])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_current_runtime_context_allowlist_is_rechecked(self) -> None:
        context = _runtime_context(allowed_routes=["wbp-other-route"])
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir), context=context)
            result = _run_dispatch_proof(paths)

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            "WBP_CONTROLLED_API_DISPATCH_HOOK_ENTRY_NOT_PROVEN",
        )
        self.assertIn("FAIL_ROUTE_NOT_ALLOWED", packet["blocking_reasons"])
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["ledger_bound_dispatch_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_ambiguous_alias_blocks_before_api_lane_call(self) -> None:
        prompt = "Codex, дай задачу DIP и Agent 2: проверь ambiguity."
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir), prompt=prompt)
            result = _run_dispatch_proof(paths, prompt=prompt)

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("INTENT_AMBIGUOUS_NO_DISPATCH", packet["blocking_reasons"])
        self.assertTrue(packet["real_user_prompt_submit_ledger_proven"])
        self.assertFalse(packet["ledger_bound_dispatch_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet, prompts=[prompt])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_manual_or_synthetic_ledger_cannot_drive_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(
                Path(temp_dir),
                origin_state="synthetic_hook_flow",
                use_event_file=False,
            )
            result = _run_dispatch_proof(paths)

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.REAL_LEDGER_BOUND_API_DISPATCH_LEDGER_NOT_PROVEN,
        )
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        self.assertFalse(packet["ledger_bound_dispatch_admitted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths, _runtime_context())
            hook_result = _run_hook(
                paths,
                origin_state="custom_codex_flow_proven",
                use_event_file=True,
            )

        hook_packet = json.loads(hook_result.stdout)
        self.assertEqual(hook_result.returncode, 1)
        self.assertFalse(hook_packet["hook_ledger_written"])
        self.assertFalse(hook_packet["user_prompt_submit_hook_ran"])
        self.assertIn(
            "custom_codex_origin_requires_stdin_transport",
            hook_packet["blocking_reasons"],
        )
        self.assertFalse(hook_packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(hook_packet), [])

    def test_provider_failure_keeps_admission_but_blocks_response_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir))
            ledger_packet = _ledger_proof_packet(paths)
            packet = _dispatch_packet(
                ledger_packet=ledger_packet,
                controlled_provider_available=False,
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], "WBP_CONTROLLED_PROVIDER_UNAVAILABLE")
        self.assertTrue(packet["ledger_bound_dispatch_admitted"])
        self.assertTrue(packet["api_lane_called"])
        self.assertFalse(packet["api_response_received"])
        self.assertFalse(packet["response_digest_bound"])
        self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
        _assert_no_handoff_ui_or_product_claim(self, packet)
        _assert_no_raw_prompt_route_or_provider(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unsafe_ledger_proof_overclaims_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _prepare_paths(Path(temp_dir))
            ledger_packet = _ledger_proof_packet(paths)

        for field in (
            "product_ready",
            "handoff_delivered",
            "custom_codex_ui_visibility_proven",
            "fallback_used",
            "local_imitation_used",
            "native_codex_subagent_used_as_dip",
            "raw_prompt_recorded",
        ):
            with self.subTest(field=field):
                unsafe = dict(ledger_packet)
                unsafe[field] = True
                packet = _dispatch_packet(ledger_packet=unsafe)

                self.assertEqual(packet["status"], "error")
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.REAL_LEDGER_BOUND_API_DISPATCH_UNSAFE_SOURCE,
                )
                self.assertFalse(packet["ledger_bound_dispatch_admitted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["api_response_received"])
                self.assertFalse(packet["real_ledger_bound_api_dispatch_proven"])
                self.assertTrue(packet["ledger_proof_unsafe_claim_failures"])
                _assert_no_handoff_ui_or_product_claim(self, packet)
                _assert_no_raw_prompt_route_or_provider(self, packet)
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_ledger_bound_dispatch_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "ledger-bound-dispatch-proof",
                "--prompt",
                PROMPT,
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
