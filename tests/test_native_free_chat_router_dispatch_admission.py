# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import native_free_chat_router_dispatch_admission as admission
from wild_boar_proxy import real_custom_codex_hook_proof as hook_proof
from wild_boar_proxy import router_hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: докажи dispatch admission."


def _runtime_context(*, allowed_routes: list[str] | None = None) -> dict[str, object]:
    allowed_routes = [ROUTE_ID] if allowed_routes is None else allowed_routes
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_launch_selection_packet",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": ["DIP", "Agent 2", "Worker"],
                "lane": "api_route",
                "enabled": True,
                "route_id": ROUTE_ID,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "alias_to_agent_id": {
            "Codex": "codex",
            "Agent 1": "codex",
            "DIP": "dip",
            "Agent 2": "dip",
            "Worker": "dip",
        },
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": allowed_routes,
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _prompt_digest(prompt: str, context: dict[str, object]) -> str:
    packet = router_hook_entry.build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=router_hook_entry.HOOK_SURFACE_USER_PROMPT_SUBMIT,
    )
    return str(packet["prompt_digest"])


def _ledger(
    *,
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    **overrides: object,
) -> dict[str, object]:
    context = _runtime_context() if context is None else context
    hook_hash = _sha256("wbp-user-prompt-submit-hook-v1")
    ledger = hook_proof.build_user_prompt_submit_hook_ledger(
        prompt_digest=_prompt_digest(prompt, context),
        runtime_context_digest_value=hook_proof.runtime_context_digest(context),
        thread_digest=_sha256("custom-codex-thread"),
        turn_digest=_sha256("custom-codex-turn"),
        trusted_hook_config_sha256=hook_hash,
        loaded_hook_config_sha256=hook_hash,
        hook_producer_state="HOOK_RAN_CUSTOM_CODEX_PROVEN",
        hook_event_digest=_sha256("custom-codex-user-prompt-submit-event"),
        session_digest=_sha256("custom-codex-session"),
        cwd_digest=_sha256(str(ROOT)),
        hook_trust_source="codex_non_managed_hook_execution",
    )
    ledger.update(overrides)
    return ledger


def _write_context_and_ledger(
    root: Path,
    *,
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    ledger_overrides: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    context = _runtime_context() if context is None else context
    profile_dir = root / "profile"
    profile_dir.mkdir()
    (profile_dir / router_hook_entry.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(context) + "\n",
        encoding="utf-8",
    )
    ledger_path = root / "user-prompt-submit-ledger.json"
    ledger_path.write_text(
        json.dumps(_ledger(prompt=prompt, context=context, **(ledger_overrides or {})))
        + "\n",
        encoding="utf-8",
    )
    return profile_dir, ledger_path


def _run_dispatch_admission(
    *,
    prompt: str,
    profile_dir: Path,
    ledger_path: Path,
    handoff_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WBP_PROFILE_DIR"] = str(profile_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "dispatch-admission",
            "--prompt",
            prompt,
            "--hook-ledger-file",
            str(ledger_path),
            "--handoff-file",
            str(handoff_path),
            "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_no_prompt_route_or_secret(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    prompt: str,
    extra_prompts: list[str] | None = None,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(ROUTE_ID, serialized)
    for item in [prompt, *(extra_prompts or [])]:
        testcase.assertNotIn(item, serialized)
        testcase.assertFalse(packet_contains_text(packet, item))
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


class NativeFreeChatRouterDispatchAdmissionTests(unittest.TestCase):
    def test_positive_cli_writes_proof_backed_handoff_file_without_product_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            handoff_path = root / "dispatch-handoff.json"
            result = _run_dispatch_admission(
                prompt=PROMPT,
                profile_dir=profile_dir,
                ledger_path=ledger_path,
                handoff_path=handoff_path,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            admission.NATIVE_FREE_CHAT_ROUTER_DISPATCH_ADMISSION_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "mutate")
        self.assertEqual(packet["changed_files"], [str(handoff_path)])
        self.assertTrue(packet["native_free_chat_router_dispatch_admission_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_producer_ledger_proven"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_response_received"])
        self.assertTrue(packet["response_bound_to_proof"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertEqual(packet["dispatch_status"], "proven")
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["provider_response_proven"])
        self.assertTrue(packet["controlled_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["source_handoff_delivered"])
        self.assertTrue(packet["source_delivery_observed"])
        self.assertTrue(packet["handoff_file_written"])
        self.assertTrue(packet["handoff_file_sha256"])
        self.assertTrue(packet["handoff_evidence_digest_bound"])
        self.assertTrue(packet["dispatch_result_digest_bound"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertEqual(packet["selected_slot"], "dip")
        self.assertTrue(packet["selected_api_route_id_present"])
        self.assertFalse(packet["live_provider_proven"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["native_free_chat_router_product_ready"])
        self.assertFalse(packet["native_free_chat_router_delivery_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_custom_codex_ui"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router_product_ready"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router_delivery"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

        self.assertEqual(
            handoff["packet_kind"],
            admission.NATIVE_FREE_CHAT_ROUTER_DISPATCH_HANDOFF_PACKET_KIND,
        )
        self.assertTrue(handoff["hook_prompt_digest_bound"])
        self.assertTrue(handoff["hook_runtime_context_digest_bound"])
        self.assertTrue(handoff["api_lane_called"])
        self.assertTrue(handoff["dispatch_result_digest_bound"])
        self.assertFalse(handoff["product_ready"])
        self.assertFalse(handoff["native_free_chat_router_proven"])
        self.assertFalse(handoff["custom_codex_ui_visibility_proven"])
        _assert_no_prompt_route_or_secret(self, handoff, prompt=PROMPT)

    def test_negative_inputs_do_not_write_handoff_or_false_green(self) -> None:
        cases = [
            (
                "prompt_mismatch",
                {},
                _runtime_context(),
                "Codex, дай задачу DIP: другой prompt.",
            ),
            (
                "unsafe_ledger_product_ready",
                {"product_ready": True},
                _runtime_context(),
                PROMPT,
            ),
            (
                "route_not_allowed",
                {},
                _runtime_context(allowed_routes=[]),
                PROMPT,
            ),
        ]
        for name, ledger_overrides, context, prompt in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        context=context,
                        ledger_overrides=ledger_overrides,
                    )
                    handoff_path = root / f"{name}-handoff.json"
                    result = _run_dispatch_admission(
                        prompt=prompt,
                        profile_dir=profile_dir,
                        ledger_path=ledger_path,
                        handoff_path=handoff_path,
                    )

                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertFalse(handoff_path.exists())
                    packet = json.loads(result.stdout)

                self.assertEqual(packet["status"], "error")
                self.assertFalse(
                    packet["native_free_chat_router_dispatch_admission_proven"]
                )
                self.assertFalse(packet["handoff_file_written"])
                self.assertEqual(packet["changed_files"], [])
                self.assertEqual(packet["dispatch_status"], "blocked")
                self.assertFalse(packet["product_ready"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertFalse(packet["custom_codex_ui_visibility_proven"])
                self.assertFalse(packet["fallback_used"])
                self.assertFalse(packet["local_imitation_used"])
                self.assertFalse(packet["native_codex_subagent_used_as_dip"])
                self.assertTrue(packet["blocking_reasons"])
                _assert_no_prompt_route_or_secret(
                    self,
                    packet,
                    prompt=PROMPT,
                    extra_prompts=[prompt] if prompt != PROMPT else None,
                )
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_dispatch_admission_as_mutate(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "dispatch-admission",
                "--prompt",
                PROMPT,
                "--hook-ledger-file",
                "/tmp/wbp-ledger.json",
                "--handoff-file",
                "/tmp/wbp-handoff.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "mutate")


if __name__ == "__main__":
    unittest.main()
