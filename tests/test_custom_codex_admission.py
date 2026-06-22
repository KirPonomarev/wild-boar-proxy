# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import textwrap
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


@contextmanager
def _mocked_provider(*, expected_text: str = EXPECTED_TEXT) -> tuple[str, ThreadingHTTPServer]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802
            self.server.request_count += 1  # type: ignore[attr-defined]
            if self.path != "/v1/chat/completions":
                self._send_json(404, {"error": "not_found"})
                return
            if self.headers.get("Authorization") != "Bearer test-key":
                self._send_json(401, {"error": "auth_failed"})
                return
            self._send_json(
                200,
                {
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": expected_text},
                        }
                    ],
                },
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), Handler)
    server.request_count = 0  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield (f"http://127.0.0.1:{server.server_port}/v1", server)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _sample_route(*, base_url: str, route_id: str = ROUTE_ID) -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": route_id,
        "display_name": "DeepSeek test route",
        "provider": "openrouter",
        "base_url": base_url,
        "endpoint_path": "/chat/completions",
        "upstream_model": "deepseek-test",
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": "paid_or_free_limited",
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


def _runtime_context(
    *,
    route_id: str = ROUTE_ID,
    file_bridge: dict[str, object] | None = None,
    allowed_route_ids: list[str] | None = None,
) -> dict[str, object]:
    context: dict[str, object] = {
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
        "allowed_api_route_ids": (
            [route_id] if allowed_route_ids is None else allowed_route_ids
        ),
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
    if file_bridge is not None:
        context["deepseek_live_format_check_file_bridge"] = file_bridge
    return context


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


def _write_profile(
    paths: RuntimePaths,
    *,
    runtime_context: dict[str, object] | None = None,
) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.managed_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    paths.runtime_effective_mode_file.write_text("stable\n", encoding="utf-8")
    paths.managed_config_file.write_text("mode: stable\n", encoding="utf-8")
    (paths.profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(runtime_context or _runtime_context()) + "\n",
        encoding="utf-8",
    )
    install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
    assert install["status"] == "ok"


def _write_external_models_registry(paths: RuntimePaths, *, base_url: str) -> Path:
    external_root = paths.managed_dir / "external-models"
    external_root.mkdir(parents=True, exist_ok=True)
    (external_root / "routes.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": [_sample_route(base_url=base_url)],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    secrets_file = external_root / "secrets.env"
    secrets_file.write_text("OPENROUTER_API_KEY=test-key\n", encoding="utf-8")
    os.chmod(secrets_file, 0o600)
    return external_root


def _file_bridge_packet(root: Path, *, route_id: str = ROUTE_ID) -> dict[str, object]:
    bridge_root = root / "file-bridge"
    return {
        "enabled": True,
        "bridge_kind": "server_owned_file_bridge",
        "network_boundary": "custom_sandbox_filesystem_to_wbp_server_then_provider",
        "request_dir": str(bridge_root / "requests"),
        "response_dir": str(bridge_root / "responses"),
        "processed_dir": str(bridge_root / "processed"),
        "request_extension": ".json",
        "response_extension": ".json",
        "model": route_id,
        "poll_interval_seconds": 0.02,
        "timeout_seconds": 5,
        "request_json_template": {
            "schema_version": 1,
            "request_id": "<unique-id>",
            "model": route_id,
            "input": "Answer exactly one line: <expected_text>",
            "stream": False,
            "max_output_tokens": 32,
            "temperature": 0,
        },
        "response_text_field": "output_text",
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


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
            if os.environ.get("WBP_FAKE_MUTATE_HOOK_STATE") == "1":
                config_path = Path(os.environ["WBP_CONFIG_TOML"])
                with config_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "\\n[hooks.state.\\"fake-hook-trust-entry\\"]\\n"
                        "trusted_hash = \\"sha256:"
                        "1111111111111111111111111111111111111111111111111111111111111111\\"\\n"
                    )
            if os.environ.get("WBP_FAKE_MUTATE_PROJECT_TRUST_STATE") == "1":
                config_path = Path(os.environ["WBP_CONFIG_TOML"])
                with config_path.open("a", encoding="utf-8") as handle:
                    handle.write(
                        "\\n[projects.\\"/Volumes/Work/wild-boar-proxy\\"]\\n"
                        "trust_level = \\"trusted\\"\\n"
                    )
            if os.environ.get("WBP_FAKE_MUTATE_CONFIG_MODEL") == "1":
                config_path = Path(os.environ["WBP_CONFIG_TOML"])
                config_path.write_text('model = "gpt-mutated"\\n', encoding="utf-8")

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
            provider_packet = _provider_packet(route_id, expected)
            provider_stdout = json.dumps(provider_packet)
            if mode == "managed_file_bridge":
                provider_result = subprocess.run(
                    live_parts,
                    cwd=os.getcwd(),
                    env=os.environ.copy(),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                provider_stdout = provider_result.stdout.strip()
                try:
                    provider_packet = json.loads(provider_stdout)
                except json.JSONDecodeError:
                    provider_packet = {
                        "status": "error",
                        "machine_error_code": "FAKE_CODEX_PROVIDER_PACKET_INVALID",
                        "changed_files": [],
                        "data": {},
                    }
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
                        "aggregated_output": provider_stdout,
                        "exit_code": 0,
                        "status": "completed",
                    },
                }
            )
            _emit(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate-call",
                        "type": "mcp_tool_call",
                        "server": "wbp",
                        "tool": "delegate_to_dip",
                        "arguments": {
                            "expected_alias": "DIP",
                            "task_sha256": producer._sha256_text(prompt),
                        },
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
                            "structured_content": structured,
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

    def test_managed_file_bridge_admission_proves_workspace_write_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            context = _runtime_context(file_bridge=_file_bridge_packet(root))
            _write_profile(paths, runtime_context=context)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with _mocked_provider(expected_text=EXPECTED_TEXT) as (base_url, provider):
                _write_external_models_registry(paths, base_url=base_url)
                with mock.patch.dict(
                    os.environ,
                    {
                        "PYTHONPATH": str(ROOT),
                        "WBP_FAKE_CODEX_MODE": "managed_file_bridge",
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
                        sandbox="workspace-write",
                        timeout_seconds=20,
                    )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["admission_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["managed_file_bridge_configured"])
        self.assertTrue(packet["managed_file_bridge_started"])
        self.assertTrue(packet["managed_file_bridge_stopped"])
        self.assertTrue(packet["managed_file_bridge_route_allowed"])
        self.assertTrue(packet["managed_file_bridge_sandbox_admitted"])
        self.assertTrue(packet["managed_file_bridge_observed"])
        self.assertTrue(packet["managed_file_bridge_response_id_bound"])
        self.assertFalse(packet["managed_file_bridge_response_request_id_recorded"])
        self.assertTrue(packet["managed_file_bridge_lifecycle_ok"])
        self.assertTrue(packet["managed_file_bridge_ok"])
        self.assertTrue(packet["server_owned_file_bridge_configured"])
        self.assertTrue(packet["server_owned_file_bridge"])
        self.assertIn("managed_file_bridge_response", packet["declared_write_surfaces"])
        self.assertTrue(packet["runtime_context_file_bridge_used"])
        self.assertTrue(packet["bridge_or_file_bridge_used"])
        self.assertEqual(packet["bridge_kind"], "server_owned_file_bridge")
        self.assertGreaterEqual(packet["managed_file_bridge_request_count"], 1)
        self.assertGreaterEqual(packet["managed_file_bridge_response_count"], 1)
        self.assertEqual(packet["managed_file_bridge_error_count"], 0)
        self.assertEqual(packet["managed_file_bridge_last_machine_error_code"], "OK")
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertTrue(packet["runtime_effective_truth_unchanged"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertEqual(provider.request_count, 1)  # type: ignore[attr-defined]
        _assert_no_raw_sensitive_text(self, packet)

    def test_file_bridge_response_event_is_normalized_to_live_provider_packet(self) -> None:
        raw_response = {
            "schema_version": 1,
            "packet_kind": "custom_native_file_bridge_response",
            "status": "ok",
            "machine_error_code": "OK",
            "request_id": "codex-test-request",
            "model": ROUTE_ID,
            "bridge_kind": "server_owned_file_bridge",
            "server_owned_file_bridge": True,
            "output_text": EXPECTED_TEXT,
            "response_text_field": "output_text",
            "fallback_used": False,
            "local_imitation_used": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        packet, observed = admission._live_provider_packet_from_events(
            [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "/bin/zsh -lc file-bridge-request",
                        "aggregated_output": json.dumps(raw_response),
                        "exit_code": 0,
                        "status": "completed",
                    },
                }
            ],
            expected_text=EXPECTED_TEXT,
        )

        data = packet["data"]
        self.assertTrue(observed)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(data["check_kind"], "api_only_live_route_format")
        self.assertEqual(data["requested_model"], ROUTE_ID)
        self.assertTrue(data["expected_text_observed"])
        self.assertEqual(data["response_preview_bounded"], EXPECTED_TEXT)
        self.assertTrue(data["runtime_context_file_bridge_used"])
        self.assertTrue(data["bridge_or_file_bridge_used"])
        self.assertEqual(data["bridge_kind"], "server_owned_file_bridge")
        self.assertFalse(data["direct_provider_auth_proven"])
        self.assertFalse(data["direct_provider_response_observed"])
        self.assertFalse(data["provider_auth_ok"])
        self.assertFalse(data["positive_provider_proof_gate_satisfied"])
        self.assertFalse(data["bridge_green_counts_as_provider_proof"])
        self.assertEqual(
            data["file_bridge_response_request_id_sha256"],
            hashlib.sha256(b"codex-test-request").hexdigest(),
        )
        self.assertNotIn("file_bridge_response_request_id", data)
        self.assertFalse(data["fallback_used"])
        self.assertFalse(data["raw_backend_details_exposed"])

    def test_file_bridge_response_without_request_id_is_not_observed(self) -> None:
        raw_response = {
            "schema_version": 1,
            "packet_kind": "custom_native_file_bridge_response",
            "status": "ok",
            "machine_error_code": "OK",
            "model": ROUTE_ID,
            "bridge_kind": "server_owned_file_bridge",
            "server_owned_file_bridge": True,
            "output_text": EXPECTED_TEXT,
            "response_text_field": "output_text",
            "fallback_used": False,
            "local_imitation_used": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }
        packet, observed = admission._live_provider_packet_from_events(
            [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "/bin/zsh -lc file-bridge-request",
                        "aggregated_output": json.dumps(raw_response),
                        "exit_code": 0,
                        "status": "completed",
                    },
                }
            ],
            expected_text=EXPECTED_TEXT,
        )

        self.assertFalse(observed)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_LIVE_PROVIDER_NOT_OBSERVED,
        )

    def test_managed_file_bridge_read_only_is_not_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            context = _runtime_context(file_bridge=_file_bridge_packet(root))
            _write_profile(paths, runtime_context=context)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with _mocked_provider(expected_text=EXPECTED_TEXT) as (base_url, _provider):
                _write_external_models_registry(paths, base_url=base_url)
                with mock.patch.dict(
                    os.environ,
                    {
                        "PYTHONPATH": str(ROOT),
                        "WBP_FAKE_CODEX_MODE": "managed_file_bridge",
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
                        sandbox="read-only",
                        timeout_seconds=20,
                    )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            admission.ADMISSION_FILE_BRIDGE_NOT_PROVEN,
        )
        self.assertFalse(packet["admission_proven"])
        self.assertTrue(packet["managed_file_bridge_configured"])
        self.assertFalse(packet["managed_file_bridge_sandbox_admitted"])
        self.assertFalse(packet["managed_file_bridge_started"])
        self.assertFalse(packet["managed_file_bridge_ok"])
        self.assertTrue(packet["server_owned_file_bridge_configured"])
        self.assertFalse(packet["server_owned_file_bridge"])
        self.assertIn("managed_file_bridge_sandbox_not_admitted", packet["blocking_reasons"])
        self.assertIn("managed_file_bridge_not_started", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        _assert_no_raw_sensitive_text(self, packet)

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

    def test_codex_hook_trust_state_write_does_not_count_as_runtime_truth_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_MUTATE_HOOK_STATE": "1",
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
        self.assertTrue(packet["runtime_effective_truth_unchanged"])
        self.assertTrue(packet["config_toml_unchanged"])
        self.assertEqual(packet["runtime_truth_mutated_surfaces"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_codex_project_trust_state_write_does_not_count_as_runtime_truth_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_MUTATE_PROJECT_TRUST_STATE": "1",
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
        self.assertTrue(packet["runtime_effective_truth_unchanged"])
        self.assertTrue(packet["config_toml_unchanged"])
        self.assertEqual(packet["runtime_truth_mutated_surfaces"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_config_toml_runtime_field_mutation_blocks_admission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            fake_codex = _write_fake_codex(root / "fake-codex")
            with mock.patch.dict(
                os.environ,
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_FAKE_MUTATE_CONFIG_MODEL": "1",
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
        self.assertFalse(packet["runtime_effective_truth_unchanged"])
        self.assertFalse(packet["config_toml_unchanged"])
        self.assertIn("config_toml", packet["runtime_truth_mutated_surfaces"])
        self.assertIn("runtime_truth_mutated:config_toml", packet["blocking_reasons"])
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
            "managed_file_bridge_ok": True,
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
            ("managed_file_bridge_ok", admission.ADMISSION_FILE_BRIDGE_NOT_PROVEN),
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
