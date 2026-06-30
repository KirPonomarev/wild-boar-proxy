# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import custom_codex_hook_origin_proof as origin_proof
from wild_boar_proxy import proof_seal
from wild_boar_proxy import real_custom_codex_hook_proof as integrated
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни доказанный API ответ."
EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"
RAW_PROVIDER_TEXT = "raw provider response must not be stored"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _input_hashes_digest(input_hashes: dict[str, str]) -> str:
    encoded = json.dumps(
        {"input_packet_hashes": input_hashes},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256(encoded)


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
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            ROUTE_ID,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _prompt_digest(prompt: str, context: dict[str, object]) -> str:
    packet = hook_entry.build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_USER_PROMPT_SUBMIT,
    )
    return str(packet["prompt_digest"])


def _hook_command(profile_dir: Path) -> str:
    script = profile_dir / producer.HOOK_SCRIPT_RELATIVE_PATH
    return f"/bin/sh {shlex.quote(str(script))}"


def _write_profile(
    root: Path,
    *,
    context: dict[str, object] | None = None,
    ledger_overrides: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object], dict[str, object]]:
    context = _runtime_context() if context is None else context
    profile_dir = root / "profile"
    profile_dir.mkdir()
    (profile_dir / producer.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(context) + "\n",
        encoding="utf-8",
    )
    script = profile_dir / producer.HOOK_SCRIPT_RELATIVE_PATH
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    command = _hook_command(profile_dir)
    hook_definition = producer.build_hook_definition(command)
    hooks_json = {"hooks": {"UserPromptSubmit": [{"hooks": [hook_definition]}]}}
    (profile_dir / producer.HOOKS_JSON_FILENAME).write_text(
        json.dumps(hooks_json) + "\n",
        encoding="utf-8",
    )
    hook_hash = producer.hook_definition_digest(command)
    ledger = integrated.build_user_prompt_submit_hook_ledger(
        prompt_digest=_prompt_digest(PROMPT, context),
        runtime_context_digest_value=integrated.runtime_context_digest(context),
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
    ledger.update(ledger_overrides or {})
    ledger_path = profile_dir / producer.HOOK_LEDGER_RELATIVE_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger) + "\n", encoding="utf-8")
    return profile_dir, context, ledger


def _live_provider_packet(
    *,
    route_id: str = ROUTE_ID,
    expected_text: str = EXPECTED_TEXT,
) -> dict[str, object]:
    return packets.build_command_packet(
        ok=True,
        human_message="External-models route live format check captured one provider response without writing state or evidence.",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra={
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
                "cost_class": "free_or_limited",
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
        },
    )


def _source_packet(
    context: dict[str, object],
    ledger: dict[str, object],
) -> dict[str, object]:
    source = integrated.build_real_custom_codex_hook_proof_packet(
        prompt_text=PROMPT,
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
        live_provider_packet=_live_provider_packet(
            route_id=str(context["agent_id_to_route"]["dip"]),
        ),
        live_provider_file_metadata={
            "live_provider_proof_file_read": True,
            "live_provider_proof_file_valid_json": True,
            "live_provider_proof_file_mapping": True,
        },
        live_provider_expected_text=EXPECTED_TEXT,
        live_provider_source_kind="file_backed_external_models_live_format_check",
        secret_values=[PROMPT, ROUTE_ID, RAW_PROVIDER_TEXT, EXPECTED_TEXT],
    )
    assert source["status"] == "ok"
    return source


def _tool_result_event(structured_content: dict[str, object]) -> dict[str, object]:
    text = json.dumps(
        structured_content,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "type": "item.completed",
        "item": {
            "id": "item-delegate-call",
            "type": "mcp_tool_call",
            "server": "wbp",
            "tool": "delegate_to_dip",
            "arguments": {
                "expected_alias": "DIP",
                "task_sha256": _sha256(PROMPT),
            },
            "status": "completed",
            "result": {
                "content": [{"type": "text", "text": text}],
                "structured_content": structured_content,
                "isError": False,
            },
        },
    }


def _assistant_event(digest: str) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-assistant-continuation",
            "type": "assistant_message",
            "role": "assistant",
            "status": "completed",
            "text": "WBP working-flow receipt.",
            "metadata": {"wbp_handoff_digest": digest},
        },
    }


def _working_flow_packet(source: dict[str, object]) -> dict[str, object]:
    structured = working_flow._safe_working_flow_delivery_payload(source)
    events = [
        {"type": "thread.started", "thread_id": "thread-working-flow"},
        {"type": "turn.started"},
        _tool_result_event(structured),
        _assistant_event(str(structured["handoff_payload_sha256"])),
        {"type": "turn.completed"},
    ]
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata={
            "integrated_live_provider_proof_file_required": True,
            "integrated_live_provider_proof_file_present": True,
            "integrated_live_provider_proof_file_read": True,
            "integrated_live_provider_proof_file_valid_json": True,
            "integrated_live_provider_proof_file_mapping": True,
            "integrated_live_provider_proof_file_error_code": "",
            "integrated_live_provider_proof_file_path_recorded": False,
            "codex_exec_jsonl_file_required": True,
            "codex_exec_jsonl_file_present": True,
            "codex_exec_jsonl_file_read": True,
            "codex_exec_jsonl_file_valid_jsonl": True,
            "codex_exec_jsonl_file_error_code": "",
            "codex_exec_jsonl_file_path_recorded": False,
            "codex_exec_jsonl_parse_error_count": 0,
            "codex_exec_event_count": len(events),
        },
        secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT],
    )
    assert packet["status"] == "ok"
    return packet


def _command_execution_event(
    source: dict[str, object],
    *,
    expected_text: str = EXPECTED_TEXT,
) -> dict[str, object]:
    provider_packet = _live_provider_packet(expected_text=expected_text)
    return {
        "type": "item.completed",
        "item": {
            "id": "item-live-format-check",
            "type": "command_execution",
            "command": (
                "/bin/zsh -lc "
                + shlex.quote(
                    f"{sys.executable} -m wild_boar_proxy external-models "
                    f"live-format-check --route {ROUTE_ID} --json"
                )
            ),
            "aggregated_output": json.dumps(provider_packet),
            "exit_code": 0,
            "status": "completed",
        },
    }


def _command_assistant_event(text: str = EXPECTED_TEXT) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-command-assistant",
            "type": "agent_message",
            "text": text,
        },
    }


def _file_bridge_command_execution_event() -> dict[str, object]:
    bridge_response = {
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
    return {
        "type": "item.completed",
        "item": {
            "id": "item-file-bridge-check",
            "type": "command_execution",
            "command": "/bin/zsh -lc file-bridge-request",
            "aggregated_output": json.dumps(bridge_response),
            "exit_code": 0,
            "status": "completed",
        },
    }


def _file_bridge_command_assistant_event() -> dict[str, object]:
    bridge_response = {
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
    return _command_assistant_event(
        "Использован live file bridge.\n\n```jsonl\n"
        + json.dumps(bridge_response, ensure_ascii=True, sort_keys=True)
        + "\n```"
    )


def _router_output_command_execution_event() -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-router-output",
            "type": "command_execution",
            "command": (
                "/bin/zsh -lc "
                + shlex.quote(
                    "python3 -m wild_boar_proxy router-hook auto-route-output "
                    "--runtime-context-file /tmp/wbp-context.json "
                    "--active-project-root /tmp/project "
                    "--repo-bridge auto --work-mode full --timeout-seconds 300 "
                    "--proof-dir /tmp/user-prompt-submit-router-proof "
                    "--prompt \"$WBP_ROUTER_PROMPT\""
                )
            ),
            "aggregated_output": EXPECTED_TEXT + "\n",
            "exit_code": 0,
            "status": "completed",
        },
    }


def _working_flow_command_packet(source: dict[str, object]) -> dict[str, object]:
    events = [
        {"type": "thread.started", "thread_id": "thread-working-flow-command"},
        {"type": "turn.started"},
        _command_execution_event(source),
        _command_assistant_event(),
        {"type": "turn.completed"},
    ]
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata={
            "integrated_live_provider_proof_file_required": True,
            "integrated_live_provider_proof_file_present": True,
            "integrated_live_provider_proof_file_read": True,
            "integrated_live_provider_proof_file_valid_json": True,
            "integrated_live_provider_proof_file_mapping": True,
            "integrated_live_provider_proof_file_error_code": "",
            "integrated_live_provider_proof_file_path_recorded": False,
            "codex_exec_jsonl_file_required": True,
            "codex_exec_jsonl_file_present": True,
            "codex_exec_jsonl_file_read": True,
            "codex_exec_jsonl_file_valid_jsonl": True,
            "codex_exec_jsonl_file_error_code": "",
            "codex_exec_jsonl_file_path_recorded": False,
            "codex_exec_jsonl_parse_error_count": 0,
            "codex_exec_event_count": len(events),
        },
    )
    assert packet["status"] == "ok"
    return packet


def _working_flow_router_output_command_packet(
    source: dict[str, object],
) -> dict[str, object]:
    events = [
        {"type": "thread.started", "thread_id": "thread-working-flow-router-output"},
        {"type": "turn.started"},
        _router_output_command_execution_event(),
        _command_assistant_event(),
        {"type": "turn.completed"},
    ]
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata={
            "integrated_live_provider_proof_file_required": True,
            "integrated_live_provider_proof_file_present": True,
            "integrated_live_provider_proof_file_read": True,
            "integrated_live_provider_proof_file_valid_json": True,
            "integrated_live_provider_proof_file_mapping": True,
            "integrated_live_provider_proof_file_error_code": "",
            "integrated_live_provider_proof_file_path_recorded": False,
            "codex_exec_jsonl_file_required": True,
            "codex_exec_jsonl_file_present": True,
            "codex_exec_jsonl_file_read": True,
            "codex_exec_jsonl_file_valid_jsonl": True,
            "codex_exec_jsonl_file_error_code": "",
            "codex_exec_jsonl_file_path_recorded": False,
            "codex_exec_jsonl_parse_error_count": 0,
            "codex_exec_event_count": len(events),
        },
    )
    assert packet["status"] == "ok"
    return packet


def _working_flow_file_bridge_command_packet(source: dict[str, object]) -> dict[str, object]:
    events = [
        {"type": "thread.started", "thread_id": "thread-working-flow-file-bridge"},
        {"type": "turn.started"},
        _file_bridge_command_execution_event(),
        _file_bridge_command_assistant_event(),
        {"type": "turn.completed"},
    ]
    packet = working_flow.build_codex_working_flow_delivery_proof_packet(
        source,
        events,
        file_metadata={
            "integrated_live_provider_proof_file_required": True,
            "integrated_live_provider_proof_file_present": True,
            "integrated_live_provider_proof_file_read": True,
            "integrated_live_provider_proof_file_valid_json": True,
            "integrated_live_provider_proof_file_mapping": True,
            "integrated_live_provider_proof_file_error_code": "",
            "integrated_live_provider_proof_file_path_recorded": False,
            "codex_exec_jsonl_file_required": True,
            "codex_exec_jsonl_file_present": True,
            "codex_exec_jsonl_file_read": True,
            "codex_exec_jsonl_file_valid_jsonl": True,
            "codex_exec_jsonl_file_error_code": "",
            "codex_exec_jsonl_file_path_recorded": False,
            "codex_exec_jsonl_parse_error_count": 0,
            "codex_exec_event_count": len(events),
        },
    )
    assert packet["status"] == "ok"
    return packet


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _run_cli(
    *,
    profile_dir: Path,
    source_path: Path,
    working_flow_path: Path,
    strict_sealed_evidence: bool = False,
    source_seal_path: Path | None = None,
    working_flow_seal_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WBP_PROFILE_DIR"] = str(profile_dir)
    args = [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "custom-origin-proof",
            "--integrated-live-provider-proof-file",
            str(source_path),
            "--working-flow-delivery-proof-file",
            str(working_flow_path),
            "--json",
    ]
    if strict_sealed_evidence:
        args.append("--strict-sealed-evidence")
        if source_seal_path is not None:
            args.extend(["--integrated-live-provider-proof-seal-file", str(source_seal_path)])
        if working_flow_seal_path is not None:
            args.extend(["--working-flow-delivery-proof-seal-file", str(working_flow_seal_path)])
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _seal_packet_cli(
    *,
    packet_path: Path,
    producer_kind: str,
    input_packet_files: list[Path] | None = None,
    runtime_context_digest: str = "",
    hook_ledger_digest: str = "",
    profile_hook_config_digest: str = "",
) -> Path:
    seal_path = proof_seal.default_seal_path(packet_path)
    args = [
        sys.executable,
        "-m",
        "wild_boar_proxy",
        "router-hook",
        "proof-seal-create",
        "--packet-file",
        str(packet_path),
        "--seal-file",
        str(seal_path),
        "--producer-kind",
        producer_kind,
        "--producer-command-digest",
        _sha256(f"{producer_kind}:command"),
        "--runtime-context-digest",
        runtime_context_digest,
        "--hook-ledger-digest",
        hook_ledger_digest,
        "--profile-hook-config-digest",
        profile_hook_config_digest,
        "--json",
    ]
    for input_path in input_packet_files or []:
        args.extend(["--input-packet-file", str(input_path)])
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return seal_path


def _write_sealed_source_and_working(
    root: Path,
    *,
    context: dict[str, object],
    ledger: dict[str, object],
) -> tuple[Path, Path, Path, Path]:
    source = _source_packet(context, ledger)
    source_path = _write_json(root / "source.packet.json", source)
    working = _working_flow_packet(source)
    working_path = _write_json(root / "working-flow.packet.json", working)
    source_seal_path = _seal_packet_cli(
        packet_path=source_path,
        producer_kind="router_hook_user_prompt_submit_proof",
        runtime_context_digest=str(source["runtime_context_digest"]),
        hook_ledger_digest=proof_seal.sha256_file(
            root / "profile" / producer.HOOK_LEDGER_RELATIVE_PATH
        ),
        profile_hook_config_digest=str(source["loaded_hook_config_sha256"]),
    )
    working_seal_path = _seal_packet_cli(
        packet_path=working_path,
        producer_kind="router_hook_working_flow_delivery_proof",
        input_packet_files=[source_path],
    )
    return source_path, working_path, source_seal_path, working_seal_path


def _assert_no_secret_or_raw_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT, RAW_PROVIDER_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    for field in (
        "raw_prompt_recorded",
        "prompt_text_recorded",
        "natural_phrase_recorded",
        "raw_jsonl_recorded",
        "tool_call_arguments_recorded",
        "route_candidate_recorded",
        "raw_route_id_recorded",
        "selected_api_route_id_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
        "raw_backend_details_exposed",
        "secret_value_exposed",
    ):
        testcase.assertFalse(packet[field])


class CustomCodexHookOriginProofTests(unittest.TestCase):
    def test_positive_proves_custom_codex_hook_origin_and_working_flow_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path = _write_json(root / "source.json", _source_packet(context, ledger))
            working_flow_path = _write_json(
                root / "working-flow.json",
                _working_flow_packet(json.loads(source_path.read_text())),
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_flow_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(
            packet["packet_kind"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_PROOF_PACKET_KIND,
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["hook_origin_truth_source"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_TRUTH_SOURCE,
        )
        self.assertTrue(packet["custom_profile_identity_bound"])
        self.assertTrue(packet["profile_runtime_context_digest_bound"])
        self.assertTrue(packet["profile_hook_config_digest_bound"])
        self.assertTrue(packet["profile_hook_script_executable"])
        self.assertTrue(packet["profile_hook_ledger_matches_source"])
        self.assertFalse(packet["profile_hook_command_origin_surface_declared"])
        self.assertEqual(packet["command_origin_surface"], "custom_codex_flow")
        self.assertTrue(packet["command_origin_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["custom_codex_origin_proven"])
        self.assertTrue(packet["native_custom_codex_flow_proven"])
        self.assertTrue(packet["native_router_hook_observed"])
        self.assertTrue(packet["user_prompt_submit_hook_observed"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_written"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["live_provider_response_digest_bound_to_handoff"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_sealed_mode_proves_source_file_authenticity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, source_seal_path, working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=source_seal_path,
                working_flow_seal_path=working_seal_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["strict_sealed_evidence"])
        self.assertTrue(packet["source_file_seal_verified"])
        self.assertTrue(packet["working_flow_file_seal_verified"])
        self.assertTrue(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["source_file_unforgeable"])
        self.assertFalse(packet["cryptographic_authenticity_proven"])
        self.assertTrue(packet["command_origin_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["seal_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_command_execution_delivery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source_path = _write_json(root / "source.json", source)
            working_flow_path = _write_json(
                root / "working-flow-command.json",
                _working_flow_command_packet(source),
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_flow_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["command_origin_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_file_bridge_command_delivery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source_path = _write_json(root / "source.json", source)
            working_flow_path = _write_json(
                root / "working-flow-file-bridge-command.json",
                _working_flow_file_bridge_command_packet(source),
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_flow_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["command_origin_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["working_flow_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_accepts_router_output_command_delivery_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source_path = _write_json(root / "source.json", source)
            working_flow_path = _write_json(
                root / "working-flow-router-output-command.json",
                _working_flow_router_output_command_packet(source),
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_flow_path,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["command_origin_proven"])
        self.assertTrue(packet["custom_codex_flow_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["working_flow_failures"], [])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_command_execution_delivery_surface_with_failure_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source_path = _write_json(root / "source.json", source)
            working_flow_packet = _working_flow_command_packet(source)
            working_flow_packet["command_execution_delivery_failures"] = [
                "forged_failure_list_must_block"
            ]
            working_flow_path = _write_json(
                root / "working-flow-command-forged.json",
                working_flow_packet,
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_flow_path,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn(
            "working_flow_command_delivery_failures_not_empty",
            packet["blocking_reasons"],
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_sealed_mode_blocks_missing_source_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, _source_seal_path, working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=root / "missing-source.seal.json",
                working_flow_seal_path=working_seal_path,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_SEAL_INVALID,
        )
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("source_proof_seal_not_verified", packet["seal_failures"])

    def test_strict_sealed_mode_blocks_unexpected_source_seal_input_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, source_seal_path, working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            seal = json.loads(source_seal_path.read_text(encoding="utf-8"))
            seal["input_packet_hashes"]["unexpected_kind"] = _sha256("unexpected")
            seal["producer_inputs_digest"] = _input_hashes_digest(
                dict(seal["input_packet_hashes"])
            )
            source_seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=source_seal_path,
                working_flow_seal_path=working_seal_path,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("source_proof_seal_not_ok", packet["seal_failures"])
        self.assertIn(
            "input_packet_hash_unexpected:unexpected_kind",
            packet["source_proof_seal_failures"],
        )

    def test_strict_sealed_mode_blocks_modified_source_packet_after_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, source_seal_path, working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            source = json.loads(source_path.read_text(encoding="utf-8"))
            source["provider_response_digest"] = _sha256("changed provider digest")
            source_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=source_seal_path,
                working_flow_seal_path=working_seal_path,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("source_proof_seal_not_ok", packet["seal_failures"])
        self.assertIn(
            "sealed_packet_sha256_mismatch",
            packet["source_proof_seal_failures"],
        )

    def test_strict_sealed_mode_blocks_wrong_packet_kind_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, source_seal_path, _working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            wrong_working_seal = _seal_packet_cli(
                packet_path=working_path,
                producer_kind="wrong_kind_test",
                input_packet_files=[],
            )
            seal = json.loads(wrong_working_seal.read_text(encoding="utf-8"))
            seal["sealed_packet_kind"] = "wrong_packet_kind"
            wrong_working_seal.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=source_seal_path,
                working_flow_seal_path=wrong_working_seal,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("working_flow_proof_seal_not_ok", packet["seal_failures"])
        self.assertIn(
            "sealed_packet_kind_mismatch",
            packet["working_flow_proof_seal_failures"],
        )

    def test_strict_sealed_mode_blocks_cross_run_working_flow_input_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, source_seal_path, working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            seal = json.loads(working_seal_path.read_text(encoding="utf-8"))
            seal["input_packet_hashes"][
                integrated.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
            ] = _sha256("other source packet")
            working_seal_path.write_text(json.dumps(seal) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
                strict_sealed_evidence=True,
                source_seal_path=source_seal_path,
                working_flow_seal_path=working_seal_path,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("working_flow_proof_seal_not_ok", packet["seal_failures"])
        self.assertIn(
            "input_packet_hash_mismatch:wbp_real_custom_codex_hook_proof",
            packet["working_flow_proof_seal_failures"],
        )

    def test_legacy_mode_keeps_source_file_authenticity_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source_path, working_path, _source_seal_path, _working_seal_path = (
                _write_sealed_source_and_working(
                    root,
                    context=context,
                    ledger=ledger,
                )
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=source_path,
                working_flow_path=working_path,
            )

        self.assertEqual(result.returncode, 0)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["strict_sealed_evidence"])
        self.assertFalse(packet["source_file_authenticity_proven"])
        self.assertFalse(packet["source_file_seal_verified"])
        self.assertTrue(packet["command_origin_proven"])

    def test_blocks_tampered_profile_hook_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            working = _working_flow_packet(source)
            hooks_path = profile_dir / producer.HOOKS_JSON_FILENAME
            hooks_doc = json.loads(hooks_path.read_text(encoding="utf-8"))
            hooks_doc["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"] = 31
            hooks_path.write_text(json.dumps(hooks_doc) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_PROFILE_INVALID,
        )
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("profile_hook_config_digest_mismatch", packet["profile_failures"])

    def test_blocks_profile_runtime_context_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            working = _working_flow_packet(source)
            changed_context = _runtime_context(allowed_routes=[ROUTE_ID, "other-route"])
            (profile_dir / producer.RUNTIME_CONTEXT_FILENAME).write_text(
                json.dumps(changed_context) + "\n",
                encoding="utf-8",
            )
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["custom_profile_identity_bound"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn(
            "profile_runtime_context_digest_mismatch",
            packet["profile_failures"],
        )

    def test_blocks_profile_ledger_prompt_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            working = _working_flow_packet(source)
            ledger_path = profile_dir / producer.HOOK_LEDGER_RELATIVE_PATH
            profile_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            profile_ledger["prompt_digest"] = _sha256("different prompt")
            ledger_path.write_text(json.dumps(profile_ledger) + "\n", encoding="utf-8")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["profile_hook_ledger_matches_source"])
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("profile_prompt_digest_mismatch", packet["profile_failures"])

    def test_blocks_missing_profile_hooks_json_runtime_context_and_ledger(self) -> None:
        cases = [
            (
                producer.HOOKS_JSON_FILENAME,
                "profile_user_prompt_submit_hook_definition_missing",
            ),
            (
                producer.RUNTIME_CONTEXT_FILENAME,
                "profile_runtime_context_file_not_read",
            ),
            (
                producer.HOOK_LEDGER_RELATIVE_PATH,
                "profile_hook_ledger_file_not_read",
            ),
        ]
        for relative_path, expected_reason in cases:
            with self.subTest(relative_path=relative_path):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, context, ledger = _write_profile(root)
                    source = _source_packet(context, ledger)
                    working = _working_flow_packet(source)
                    (profile_dir / relative_path).unlink()
                    result = _run_cli(
                        profile_dir=profile_dir,
                        source_path=_write_json(root / "source.json", source),
                        working_flow_path=_write_json(root / "working.json", working),
                    )

                self.assertEqual(result.returncode, 1)
                packet = json.loads(result.stdout)
                self.assertFalse(packet["custom_profile_identity_bound"])
                self.assertFalse(packet["command_origin_proven"])
                self.assertIn(expected_reason, packet["profile_failures"])

    def test_blocks_working_flow_delivery_not_proven(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            working = _working_flow_packet(source)
            working["codex_working_flow_delivery_proven"] = False
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_DELIVERY_INVALID,
        )
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("working_flow_delivery_not_proven", packet["working_flow_failures"])

    def test_blocks_source_and_working_flow_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            working = _working_flow_packet(source)
            working["live_provider_response_digest"] = _sha256("different response")
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_JOIN_INVALID,
        )
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn("live_provider_response_digest_mismatch", packet["join_failures"])

    def test_blocks_source_without_file_backed_live_provider_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source["live_provider_proof_file_read"] = False
            working = _working_flow_packet(_source_packet(context, ledger))
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["command_origin_proven"])
        self.assertFalse(packet["custom_profile_identity_bound"])
        self.assertTrue(packet["custom_profile_identity_inputs_valid"])
        self.assertIn(
            "source_live_provider_proof_file_not_read",
            packet["source_failures"],
        )

    def test_blocks_source_custom_origin_preclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source["custom_codex_flow_proven"] = True
            source["command_origin_proven"] = True
            working = _working_flow_packet(_source_packet(context, ledger))
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertFalse(packet["command_origin_proven"])
        self.assertIn(
            "integrated_proof_must_not_preclaim_custom_origin",
            packet["source_failures"],
        )
        self.assertIn(
            "integrated_proof_must_not_preclaim_command_origin",
            packet["source_failures"],
        )

    def test_blocks_product_ready_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, context, ledger = _write_profile(root)
            source = _source_packet(context, ledger)
            source["product_ready"] = True
            working = _working_flow_packet(_source_packet(context, ledger))
            result = _run_cli(
                profile_dir=profile_dir,
                source_path=_write_json(root / "source.json", source),
                working_flow_path=_write_json(root / "working.json", working),
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(
            packet["machine_error_code"],
            origin_proof.CUSTOM_CODEX_HOOK_ORIGIN_UNSAFE_CLAIM,
        )
        self.assertFalse(packet["command_origin_proven"])
        self.assertFalse(packet["custom_profile_identity_bound"])
        self.assertTrue(packet["custom_profile_identity_inputs_valid"])
        self.assertIn("product_ready_must_not_be_claimed", packet["unsafe_claim_failures"])


if __name__ == "__main__":
    unittest.main()
