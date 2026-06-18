# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from wild_boar_proxy import custom_codex_admission as admission
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimePaths


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни доказанный API ответ."
EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"


def _runtime_context(*, route_id: str = ROUTE_ID) -> dict[str, object]:
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
                "route_id": route_id,
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
        "agent_id_to_route": {"dip": route_id},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": [route_id],
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            route_id,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=managed / "stable-runtime-launcher.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed / "stable-runtime-config.generated.yaml",
    )


def _write_profile(paths: RuntimePaths) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.managed_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    paths.runtime_effective_mode_file.write_text("stable\n", encoding="utf-8")
    paths.managed_config_file.write_text("mode: stable\n", encoding="utf-8")
    (paths.profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(_runtime_context()) + "\n",
        encoding="utf-8",
    )
    install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
    assert install["status"] == "ok"


def _write_fake_codex(path: Path) -> Path:
    path.write_text(
        f"#!{sys.executable}\n"
        +
        textwrap.dedent(
            """\
            from __future__ import annotations

            import json
            import os
            from pathlib import Path
            import shlex
            import subprocess
            import sys

            from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
            from wild_boar_proxy import real_custom_codex_hook_proof as integrated
            from wild_boar_proxy import user_prompt_submit_hook_producer as producer

            def _emit(event: dict[str, object]) -> None:
                print(json.dumps(event, ensure_ascii=True), flush=True)

            def _provider_packet(route_id: str, expected_text: str) -> dict[str, object]:
                return {
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "External-models route live format check captured one provider response without writing state or evidence.",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "effect": "probe",
                    "data": {
                        "check_kind": "api_only_live_route_format",
                        "network_dependent": True,
                        "verification_scope": "route_provider_only_no_write",
                        "route_state": "live_response_observed_no_write",
                        "requested_model": route_id,
                        "effective_model": "deepseek-test",
                        "provider": "deepseek",
                        "fallback_used": False,
                        "fallback_chain": [route_id],
                        "latency_ms": 12,
                        "request_count": 1,
                        "retry_count": 0,
                        "parallel_fanout_attempted": False,
                        "expected_text": expected_text,
                        "expected_text_observed": True,
                        "response_preview_bounded": expected_text,
                        "response_text_length": len(expected_text),
                        "changed_files": [],
                        "state_written": False,
                        "evidence_written": False,
                        "file_mutation_attempted": False,
                        "commands_started_by_provider": False,
                        "codex_history_sent": False,
                        "repo_context_sent": False,
                        "request_shape": "openai_chat_messages",
                        "response_shape": "choices_message",
                    },
                    "raw_provider_response_recorded": False,
                }

            profile = Path(os.environ["CODEX_HOME"])
            prompt = sys.argv[-1]
            expected = os.environ.get("WBP_FAKE_EXPECTED_TEXT", "WBP_DIP_DISPATCH_OK")
            mode = os.environ.get("WBP_FAKE_CODEX_MODE", "ok")
            context = json.loads((profile / "wbp-agent-runtime-context.json").read_text())
            route_id = context["agent_id_to_route"]["dip"]
            hooks = json.loads((profile / "hooks.json").read_text())
            hook_command = hooks["hooks"]["UserPromptSubmit"][-1]["hooks"][0]["command"]
            event_prompt = prompt
            if mode == "hook_mismatch":
                event_prompt = prompt + " tampered hook prompt"
            event = {
                "session_id": "fake-custom-codex-session",
                "turn_id": "fake-custom-codex-turn",
                "cwd": os.getcwd(),
                "hook_event_name": "UserPromptSubmit",
                "model": "gpt-5.4",
                "permission_mode": "never",
                "prompt": event_prompt,
            }
            hook_env = os.environ.copy()
            if mode == "missing_run_id":
                hook_env.pop("WBP_ADMISSION_RUN_ID", None)
            hook_result = subprocess.run(
                hook_command,
                input=json.dumps(event),
                shell=True,
                text=True,
                capture_output=True,
                env=hook_env,
                check=False,
            )
            if hook_result.returncode != 0:
                sys.stderr.write(hook_result.stderr)
                sys.exit(hook_result.returncode)

            if os.environ.get("WBP_FAKE_MUTATE_RUNTIME") == "1":
                Path(os.environ["WBP_RUNTIME_EFFECTIVE_MODE_FILE"]).write_text("mutated\\n")

            provider_packet = _provider_packet(route_id, expected)
            ledger = json.loads(
                (profile / producer.HOOK_LEDGER_RELATIVE_PATH).read_text()
            )
            source = integrated.build_real_custom_codex_hook_proof_packet(
                prompt_text=prompt,
                runtime_context=context,
                hook_ledger=ledger,
                context_file_metadata={
                    "runtime_context_file_read": True,
                    "runtime_context_file_valid_json": True,
                    "runtime_context_file_mapping": True,
                },
                hook_ledger_file_metadata={
                    "hook_ledger_file_read": True,
                    "hook_ledger_file_valid_json": True,
                    "hook_ledger_file_mapping": True,
                },
                live_provider_packet=provider_packet,
                live_provider_file_metadata={
                    "live_provider_proof_file_read": True,
                    "live_provider_proof_file_valid_json": True,
                    "live_provider_proof_file_mapping": True,
                },
                live_provider_expected_text=expected,
                live_provider_source_kind="file_backed_external_models_live_format_check",
            )
            structured = working_flow._safe_working_flow_delivery_payload(source)
            cli_parts = list(context["deepseek_live_format_check_cli_command"])
            live_parts = (
                cli_parts[:-1]
                + [
                    "--prompt",
                    "Answer exactly one line: " + expected,
                    "--expected-text",
                    expected,
                ]
                + [cli_parts[-1]]
            )
            if mode == "echo_provider":
                command = "/bin/echo " + shlex.quote(expected)
            else:
                command = "/bin/zsh -lc " + json.dumps(shlex.join(live_parts))
            assistant_text = "WBP working-flow receipt."
            assistant_metadata = {"wbp_handoff_digest": structured["handoff_payload_sha256"]}
            if mode == "bad_assistant":
                assistant_text = "not bound"
                assistant_metadata = {}

            _emit({"type": "thread.started", "thread_id": "fake-custom-thread"})
            _emit({"type": "turn.started"})
            _emit(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-live-format-check",
                        "type": "command_execution",
                        "command": command,
                        "aggregated_output": json.dumps(provider_packet),
                        "exit_code": 0,
                        "status": "completed",
                    },
                }
            )
            _emit(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate-result",
                        "type": "mcp_tool_result",
                        "server_name": "wbp",
                        "tool_name": "delegate_to_dip",
                        "status": "completed",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        structured,
                                        ensure_ascii=True,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    ),
                                }
                            ],
                            "structuredContent": structured,
                            "isError": False,
                        },
                    },
                }
            )
            if mode != "bad_assistant":
                _emit(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-assistant-continuation",
                            "type": "assistant_message",
                            "role": "assistant",
                            "status": "completed",
                            "text": assistant_text,
                            "metadata": assistant_metadata,
                        },
                    }
                )
                _emit(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-command-assistant",
                            "type": "agent_message",
                            "text": expected,
                        },
                    }
                )
            else:
                _emit(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item-assistant-continuation",
                            "type": "assistant_message",
                            "role": "assistant",
                            "status": "completed",
                            "text": assistant_text,
                            "metadata": assistant_metadata,
                        },
                    }
                )
            _emit({"type": "turn.completed"})
            """
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _assert_no_raw_sensitive_text(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class CustomCodexAdmissionTests(unittest.TestCase):
    def test_codex_exec_command_accepts_explicit_model_without_rewriting_prompt(self) -> None:
        command = admission._codex_exec_command(
            codex_bin="/tmp/codex",
            codex_cwd=ROOT,
            sandbox="danger-full-access",
            codex_model="gpt-5.4",
            prompt_text=PROMPT,
        )

        self.assertEqual(command[0], "/tmp/codex")
        self.assertEqual(command[1], "exec")
        self.assertIn("-m", command)
        self.assertEqual(command[command.index("-m") + 1], "gpt-5.4")
        self.assertEqual(command[-1], PROMPT)

    def test_runner_env_selects_server_owned_external_registry_matching_context_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            home = root / "home"
            external_root = home / ".wild-boar-proxy" / "external-models"
            external_root.mkdir(parents=True)
            (external_root / "routes.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "routes": [
                            {
                                "route_id": ROUTE_ID,
                                "provider": "deepseek",
                                "enabled": True,
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.dict(os.environ, {"HOME": str(home)}, clear=False):
                os.environ.pop("WBP_EXTERNAL_MODELS_DIR", None)
                env = admission._runner_env(paths, _runtime_context())

        self.assertEqual(env["WBP_EXTERNAL_MODELS_DIR"], str(external_root))

    def test_positive_runner_proves_repeatable_admission_without_product_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
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
        self.assertTrue(packet["admission_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["same_turn_proof_runner_v1"])
        self.assertTrue(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["run_id_bound"])
        self.assertTrue(packet["admission_run_id_digest_bound"])
        self.assertFalse(packet["admission_run_id_recorded"])
        self.assertTrue(packet["session_or_turn_digest_bound"])
        self.assertTrue(packet["session_digest_bound_to_source"])
        self.assertTrue(packet["thread_digest_bound_to_source"])
        self.assertTrue(packet["turn_digest_bound_to_source"])
        self.assertTrue(packet["prompt_digest_bound"])
        self.assertTrue(packet["runtime_context_digest_bound"])
        self.assertTrue(packet["hook_ledger_fresh"])
        self.assertTrue(packet["hook_ledger_sha256"])
        self.assertTrue(packet["source_proof_sha256"])
        self.assertTrue(packet["working_flow_proof_sha256"])
        self.assertTrue(packet["origin_proof_sha256"])
        self.assertTrue(packet["codex_exec_transcript_bound"])
        self.assertTrue(packet["same_codex_exec_jsonl_bound"])
        self.assertTrue(packet["source_seal_input_hashes_bound"])
        self.assertTrue(packet["source_seal_declared_input_packet_hashes_empty"])
        self.assertTrue(packet["source_seal_runtime_context_digest_bound"])
        self.assertTrue(packet["source_seal_hook_ledger_digest_bound"])
        self.assertTrue(packet["source_seal_profile_hook_config_digest_bound"])
        self.assertTrue(packet["working_flow_seal_input_hashes_bound"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_bound"])
        self.assertTrue(packet["runtime_context_bound"])
        self.assertTrue(packet["server_issued_cli_command_bound"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
        self.assertTrue(packet["strict_sealed_evidence"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(packet["same_turn_binding_failures"], [])
        changed_names = {Path(path).name for path in packet["changed_files"]}
        self.assertIn("codex-exec.jsonl", changed_names)
        self.assertIn("custom-codex-admission.packet.json", changed_names)
        self.assertIn("custom-origin-proof.strict-sealed.packet.json", changed_names)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_missing_admission_run_id_digest_blocks_same_turn_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_CODEX_MODE": "missing_run_id",
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["admission_run_id_digest_bound"])
        self.assertIn("admission_run_id_digest_not_bound", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_echo_provider_command_does_not_get_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_CODEX_MODE": "echo_provider",
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_LIVE_PROVIDER_NOT_OBSERVED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn("live_provider_packet_not_observed", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_transcript_digest_mismatch_blocks_same_turn_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_working_flow = admission.run_codex_working_flow_delivery_proof_command

            def forged_working_flow(*args: object, **kwargs: object) -> dict[str, object]:
                packet = dict(original_working_flow(*args, **kwargs))
                packet["codex_exec_transcript_sha256"] = "f" * 64
                return packet

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "run_codex_working_flow_delivery_proof_command",
                side_effect=forged_working_flow,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["codex_exec_transcript_bound"])
        self.assertFalse(packet["same_codex_exec_jsonl_bound"])
        self.assertIn("codex_exec_transcript_not_bound", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_runtime_effective_truth_mutation_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_MUTATE_RUNTIME": "1",
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_RUNTIME_TRUTH_MUTATED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["runtime_effective_truth_unchanged"])
        self.assertIn(
            "runtime_truth_mutated:runtime_effective_mode",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])

    def test_hook_digest_mismatch_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_CODEX_MODE": "hook_mismatch",
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_HOOK_PROOF_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["hook_prompt_digest_bound"])
        self.assertIn("user_prompt_submit_proof_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_unbound_assistant_continuation_blocks_working_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_CODEX_MODE": "bad_assistant",
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_WORKING_FLOW_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertIn("working_flow_delivery_proof_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_seal_failure_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_verify = admission.verify_proof_seal

            def fail_first_seal_verify(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], dict[str, object]]:
                packet, seal = original_verify(*args, **kwargs)
                if (
                    kwargs.get("expected_packet_kind")
                    == admission.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
                ):
                    packet = dict(packet)
                    packet.update(
                        {
                            "status": "error",
                            "machine_error_code": "WBP_TEST_SEAL_VERIFY_FAILED",
                        }
                    )
                return packet, seal

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "verify_proof_seal",
                side_effect=fail_first_seal_verify,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], admission.ADMISSION_SEAL_FAILED)
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["proof_seal_verified"])
        self.assertIn("source_proof_seal_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_same_turn_input_hash_mismatch_blocks_admission_even_when_seal_status_is_ok(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_verify = admission.verify_proof_seal

            def forge_working_input_digest(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], dict[str, object]]:
                packet, seal = original_verify(*args, **kwargs)
                if (
                    kwargs.get("expected_packet_kind")
                    == admission.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND
                ):
                    packet = dict(packet)
                    packet.update(
                        {
                            "status": "ok",
                            "proof_seal_verified": True,
                            "machine_error_code": "OK",
                            "seal_input_packet_hashes_digest": "f" * 64,
                        }
                    )
                return packet, seal

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "verify_proof_seal",
                side_effect=forge_working_input_digest,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertFalse(packet["working_flow_seal_input_hashes_bound"])
        self.assertIn(
            "working_flow_seal_input_hashes_not_bound",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "working_flow_seal_input_hashes_not_bound",
            packet["same_turn_binding_failures"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_source_seal_runtime_digest_mismatch_blocks_same_turn_admission(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_verify = admission.verify_proof_seal

            def forge_source_runtime_digest(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], dict[str, object]]:
                packet, seal = original_verify(*args, **kwargs)
                if (
                    kwargs.get("expected_packet_kind")
                    == admission.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
                ):
                    packet = dict(packet)
                    packet.update(
                        {
                            "status": "ok",
                            "proof_seal_verified": True,
                            "machine_error_code": "OK",
                            "runtime_context_digest": "f" * 64,
                        }
                    )
                return packet, seal

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "verify_proof_seal",
                side_effect=forge_source_runtime_digest,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertFalse(packet["source_seal_runtime_context_digest_bound"])
        self.assertIn(
            "source_seal_runtime_context_digest_not_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_source_seal_hook_ledger_digest_mismatch_blocks_same_turn_admission(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_verify = admission.verify_proof_seal

            def forge_source_hook_ledger_digest(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], dict[str, object]]:
                packet, seal = original_verify(*args, **kwargs)
                if (
                    kwargs.get("expected_packet_kind")
                    == admission.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
                ):
                    packet = dict(packet)
                    packet.update(
                        {
                            "status": "ok",
                            "proof_seal_verified": True,
                            "machine_error_code": "OK",
                            "hook_ledger_digest": "f" * 64,
                        }
                    )
                return packet, seal

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "verify_proof_seal",
                side_effect=forge_source_hook_ledger_digest,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertFalse(packet["source_seal_hook_ledger_digest_bound"])
        self.assertIn(
            "source_seal_hook_ledger_digest_not_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_source_seal_profile_hook_config_digest_mismatch_blocks_same_turn_admission(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            original_verify = admission.verify_proof_seal

            def forge_source_profile_hook_config_digest(
                *args: object,
                **kwargs: object,
            ) -> tuple[dict[str, object], dict[str, object]]:
                packet, seal = original_verify(*args, **kwargs)
                if (
                    kwargs.get("expected_packet_kind")
                    == admission.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
                ):
                    packet = dict(packet)
                    packet.update(
                        {
                            "status": "ok",
                            "proof_seal_verified": True,
                            "machine_error_code": "OK",
                            "profile_hook_config_digest": "f" * 64,
                        }
                    )
                return packet, seal

            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "verify_proof_seal",
                side_effect=forge_source_profile_hook_config_digest,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_SAME_TURN_BINDING_FAILED,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertFalse(packet["source_seal_profile_hook_config_digest_bound"])
        self.assertIn(
            "source_seal_profile_hook_config_digest_not_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_origin_failure_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            origin_error = packets.build_command_packet(
                ok=False,
                human_message="Origin proof blocked by test.",
                machine_error_code="WBP_TEST_ORIGIN_FAILED",
                liveness="not_applicable",
                severity="recoverable",
                operator_action="stop",
                changed_files=[],
                effect="probe",
                extra={
                    "packet_kind": admission.CUSTOM_CODEX_HOOK_ORIGIN_PROOF_PACKET_KIND,
                    "custom_codex_flow_proven": False,
                    "strict_sealed_evidence": False,
                    "source_file_authenticity_proven": False,
                },
            )
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                },
            ), mock.patch.object(
                admission,
                "run_custom_codex_hook_origin_proof_command",
                return_value=origin_error,
            ):
                packet = admission.run_custom_codex_admission_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(fake_codex),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(ROOT),
                    expected_text=EXPECTED_TEXT,
                    timeout_seconds=20,
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], admission.ADMISSION_ORIGIN_FAILED)
        self.assertFalse(packet["admission_proven"])
        self.assertFalse(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["custom_codex_flow_proven"])
        self.assertIn("custom_origin_proof_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_machine_error_code_matrix_is_fail_closed(self) -> None:
        base = {
            "codex_exit_ok": True,
            "provider_observed": True,
            "source_ok": True,
            "working_ok": True,
            "source_seal_ok": True,
            "working_seal_ok": True,
            "origin_ok": True,
            "same_turn_ok": True,
            "runtime_truth_ok": True,
            "unsafe": False,
        }

        self.assertEqual(admission._machine_error_code(**base), admission.ADMISSION_OK)
        cases = [
            ("unsafe", admission.ADMISSION_UNSAFE_PACKET),
            ("runtime_truth_ok", admission.ADMISSION_RUNTIME_TRUTH_MUTATED),
            ("codex_exit_ok", admission.ADMISSION_CODEX_LAUNCH_FAILED),
            ("provider_observed", admission.ADMISSION_LIVE_PROVIDER_NOT_OBSERVED),
            ("source_ok", admission.ADMISSION_HOOK_PROOF_FAILED),
            ("working_ok", admission.ADMISSION_WORKING_FLOW_FAILED),
            ("source_seal_ok", admission.ADMISSION_SEAL_FAILED),
            ("working_seal_ok", admission.ADMISSION_SEAL_FAILED),
            ("origin_ok", admission.ADMISSION_ORIGIN_FAILED),
            ("same_turn_ok", admission.ADMISSION_SAME_TURN_BINDING_FAILED),
        ]
        for key, expected in cases:
            values = dict(base)
            values[key] = True if key == "unsafe" else False
            with self.subTest(key=key):
                self.assertEqual(admission._machine_error_code(**values), expected)

    def test_cli_admission_emits_strict_json_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_PROFILE_DIR": str(paths.profile_dir),
                    "WBP_MANAGED_DIR": str(paths.managed_dir),
                    "WBP_CONFIG_TOML": str(paths.config_toml),
                    "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                        paths.runtime_effective_mode_file
                    ),
                    "WBP_MANAGED_CONFIG_FILE": str(paths.managed_config_file),
                    "WBP_STATE_FILE": str(paths.state_file),
                    "WBP_FAKE_EXPECTED_TEXT": EXPECTED_TEXT,
                }
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "admission",
                    "--prompt",
                    PROMPT,
                    "--codex-bin",
                    str(fake_codex),
                    "--proof-dir",
                    str(root / "proof"),
                    "--codex-cwd",
                    str(ROOT),
                    "--expected-text",
                    EXPECTED_TEXT,
                    "--timeout-seconds",
                    "20",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["packet_kind"], admission.CUSTOM_CODEX_ADMISSION_PACKET_KIND)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["admission_proven"])
        self.assertTrue(packet["same_turn_custom_codex_flow_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )
