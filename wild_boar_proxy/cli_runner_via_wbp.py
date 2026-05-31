# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any


CONTOUR_ID = "WBP_CODEX_CLI_RUNNER_VIA_WBP_SMOKE_R1"
PASS_STATUS = "CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP"
PRIMARY_MODEL_ID = "gpt-5.4-mini"
REQUIRED_TRACE_PATH = "/v1/responses"
REQUIRED_CLI_RUNNER_R1_PACKETS = (
    "sync_gate_packet.json",
    "historical_dirt_quarantine_packet.json",
    "declared_write_surfaces_packet.json",
    "version_pinning_packet.json",
    "no_ambient_authority_packet.json",
    "provider_auth_strategy_reference_packet.json",
    "model_availability_reference_packet.json",
    "cli_runner_admission_packet.json",
    "cli_runner_invocation_packet.json",
    "cli_runner_command_contract_packet.json",
    "cli_runner_auth_boundary_packet.json",
    "cli_runner_request_shape_packet.json",
    "cli_runner_response_packet.json",
    "cli_runner_failure_classification_packet.json",
    "cli_runner_wbp_trace_correlation_packet.json",
    "cli_runner_non_native_boundary_packet.json",
    "cli_runner_summary_packet.json",
    "cli_runner_command_packet.json",
    "cli_runner_smoke_packet.json",
    "cli_runner_route_trace_packet.json",
    "cli_runner_response_hash_packet.json",
    "cli_runner_layer_boundary_packet.json",
    "route_account_mutation_guard_packet.json",
    "secret_redaction_audit.json",
    "cli_runner_false_green_audit.json",
    "independent_cli_runner_audit.json",
    "verification_results_packet.json",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_cli_runner_layer_boundary_packet() -> dict[str, Any]:
    return {
        "contour_id": CONTOUR_ID,
        "proves": [
            "codex_cli_runner_process_can_use_wbp_provider_endpoint",
            "isolated_codex_home_config_can_select_wbp_provider",
            "auth_command_invoked_for_local_wbp_bearer",
            "wbp_trace_observed_v1_responses",
        ],
        "does_not_prove": [
            "native_codex_app_usability",
            "original_codex_reversibility",
            "direct_egress_absence",
            "codex_app_acceptance",
            "model_availability_expansion",
            "streaming_compatibility",
            "tool_loop_compatibility",
            "full_responses_wire_compatibility",
            "final_e2e",
        ],
        "cli_runner_route_proof_is_responses_wire_compatibility": False,
        "cli_runner_route_proof_is_model_availability_expansion": False,
        "cli_runner_response_is_native_codex_app_response": False,
        "native_app_claimed": False,
        "original_codex_lane_claimed": False,
        "model_availability_reproof_claimed": False,
        "codex_app_acceptance_claimed": False,
        "streaming_claimed": False,
        "tool_loop_claimed": False,
        "direct_egress_absence_claimed": False,
        "final_e2e_claimed": False,
    }


def build_codex_auth_command_config(
    *,
    base_url: str,
    auth_command_path: str,
    model_id: str = PRIMARY_MODEL_ID,
) -> str:
    return "\n".join(
        [
            f'model = "{model_id}"',
            'model_provider = "wbp"',
            'approval_policy = "never"',
            'sandbox_mode = "read-only"',
            "disable_response_storage = true",
            "",
            "[model_providers.wbp]",
            'name = "Wild Boar Proxy"',
            f'base_url = "{base_url}"',
            'wire_api = "responses"',
            "requires_openai_auth = false",
            "",
            "[model_providers.wbp.auth]",
            f'command = "{auth_command_path}"',
            "",
        ]
    )


def build_no_ambient_authority_packet(
    *,
    env: dict[str, str],
    home: Path,
    codex_home: Path,
    auth_command_path: Path,
) -> dict[str, Any]:
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    wbp_runtime_keys = sorted(key for key in env if key.startswith("WBP_"))
    return {
        "contour_id": CONTOUR_ID,
        "home": str(home),
        "codex_home": str(codex_home),
        "home_is_isolated": Path(env.get("HOME", "")) == home,
        "codex_home_is_isolated": Path(env.get("CODEX_HOME", "")) == codex_home,
        "openai_api_key_present": "OPENAI_API_KEY" in env,
        "proxy_env_present": [key for key in proxy_keys if key in env],
        "auth_command_path": str(auth_command_path),
        "auth_command_server_owned": auth_command_path.is_absolute()
        and auth_command_path.exists()
        and auth_command_path.name == "wbp_codex_auth_command.py",
        "token_command_runtime_keys": wbp_runtime_keys,
        "runner_command_path_repo_owned": True,
        "home_strategy": "isolated_temp_home",
        "codex_home_strategy": "isolated_temp_codex_home",
        "openai_api_key_absent_or_ignored": "OPENAI_API_KEY" not in env,
        "proxy_env_absent_or_ignored": not [key for key in proxy_keys if key in env],
        "browser_supplied_authority": False,
        "remote_client_supplied_authority": False,
        "raw_token_recorded": False,
        "raw_auth_header_recorded": False,
        "status": (
            "passed"
            if Path(env.get("HOME", "")) == home
            and Path(env.get("CODEX_HOME", "")) == codex_home
            and "OPENAI_API_KEY" not in env
            and not [key for key in proxy_keys if key in env]
            else "failed"
        ),
    }


def build_trace_acceptance_packet(trace_packet: dict[str, Any]) -> dict[str, Any]:
    request_hash = str(trace_packet.get("request_body_sha256") or "")
    response_hash = str(trace_packet.get("response_body_sha256") or "")
    passed = (
        trace_packet.get("request_observed") is True
        and trace_packet.get("response_observed") is True
        and trace_packet.get("forwarded_to_wbp") is True
        and trace_packet.get("path") == REQUIRED_TRACE_PATH
        and trace_packet.get("upstream_status") == 200
        and len(request_hash) == 64
        and len(response_hash) == 64
        and trace_packet.get("prompt_body_recorded") is False
        and trace_packet.get("auth_header_recorded") is False
        and trace_packet.get("secret_value_recorded") is False
    )
    route_trace_state = "route_trace_observed" if passed else (
        "route_trace_unavailable_with_reason"
        if trace_packet.get("request_observed") is not True
        else "blocked_with_reason"
    )
    return {
        "contour_id": CONTOUR_ID,
        "status": "passed" if passed else "failed",
        "route_trace_state": route_trace_state,
        "exit_code_counted_as_route_proof": False,
        "stdout_text_counted_as_route_proof": False,
        "request_observed": trace_packet.get("request_observed") is True,
        "response_observed": trace_packet.get("response_observed") is True,
        "forwarded_to_wbp": trace_packet.get("forwarded_to_wbp") is True,
        "path": trace_packet.get("path"),
        "upstream_status": trace_packet.get("upstream_status"),
        "request_body_sha256": request_hash,
        "response_body_sha256": response_hash,
        "prompt_body_recorded": trace_packet.get("prompt_body_recorded"),
        "auth_header_recorded": trace_packet.get("auth_header_recorded"),
        "secret_value_recorded": trace_packet.get("secret_value_recorded"),
        "raw_account_id_recorded": trace_packet.get("raw_account_id_recorded"),
        "raw_backend_id_recorded": trace_packet.get("raw_backend_id_recorded"),
        "full_wire_claimed": False,
        "responses_wire_compatibility_claimed": False,
        "codex_app_acceptance_claimed": False,
    }


def build_cli_runner_claims_packet(
    *,
    probe_status: str,
    model_id: str,
    response_match_observed: bool,
    auth_command_invoked: bool,
    trace_acceptance_packet: dict[str, Any],
) -> dict[str, Any]:
    passed = (
        probe_status == "passed"
        and bool(model_id)
        and response_match_observed
        and auth_command_invoked
        and trace_acceptance_packet.get("status") == "passed"
    )
    return {
        "contour_id": CONTOUR_ID,
        "status": "passed" if passed else "failed",
        "pass_status": PASS_STATUS if passed else "",
        "consumer_kind": "codex_cli_runner",
        "native_app_claimed": False,
        "original_codex_lane_claimed": False,
        "response_accepted_by_codex_app": False,
        "selected_model_id": model_id,
        "model_claim_level": (
            "cli_runner_non_stream_wbp_200_proven"
            if passed
            else "unproven"
        ),
        "model_availability_expansion_claimed": False,
        "model_availability_reproved_in_this_contour": False,
        "new_model_availability_claims_allowed": False,
        "response_match_observed": response_match_observed,
        "response_hash_recorded_is_semantic_quality": False,
        "auth_command_invoked": auth_command_invoked,
        "streaming_claimed": False,
        "tool_loop_claimed": False,
        "direct_egress_absence_claimed": False,
        "final_e2e_claimed": False,
    }


def build_false_green_audit_packet(
    *,
    layer_boundary_packet: dict[str, Any],
    env_packet: dict[str, Any],
    trace_packet: dict[str, Any],
    claims_packet: dict[str, Any],
    original_integrity_passed: bool,
    cleanup_passed: bool,
) -> dict[str, Any]:
    checks = {
        "native_not_claimed": layer_boundary_packet.get("native_app_claimed") is False
        and claims_packet.get("native_app_claimed") is False,
        "original_not_claimed": claims_packet.get("original_codex_lane_claimed") is False,
        "ambient_authority_blocked": env_packet.get("status") == "passed",
        "trace_hashes_present": trace_packet.get("status") == "passed",
        "trace_not_exit_code_only": trace_packet.get("exit_code_counted_as_route_proof") is False,
        "route_trace_not_wire_compat": trace_packet.get("responses_wire_compatibility_claimed") is False,
        "codex_app_acceptance_not_claimed": claims_packet.get("response_accepted_by_codex_app") is False,
        "model_availability_not_reproved": claims_packet.get("model_availability_reproved_in_this_contour") is False,
        "response_match_not_substituted_for_wire": claims_packet.get("streaming_claimed") is False
        and claims_packet.get("tool_loop_claimed") is False,
        "direct_egress_not_claimed": claims_packet.get("direct_egress_absence_claimed")
        is False,
        "original_config_auth_unchanged": original_integrity_passed,
        "cleanup_passed": cleanup_passed,
    }
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "contour_id": CONTOUR_ID,
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "failed_checks": failed,
        "false_green_policy": "impossible_by_construction",
    }


def validate_cli_runner_contour_packets(packets: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for name in REQUIRED_CLI_RUNNER_R1_PACKETS:
        if name not in packets:
            findings.append(f"missing.{name}")
    layer = packets.get("cli_runner_layer_boundary_packet.json")
    if isinstance(layer, dict):
        for field in (
            "native_app_claimed",
            "original_codex_lane_claimed",
            "model_availability_reproof_claimed",
            "codex_app_acceptance_claimed",
            "streaming_claimed",
            "tool_loop_claimed",
            "direct_egress_absence_claimed",
            "final_e2e_claimed",
            "cli_runner_route_proof_is_responses_wire_compatibility",
            "cli_runner_route_proof_is_model_availability_expansion",
            "cli_runner_response_is_native_codex_app_response",
        ):
            if layer.get(field) is not False:
                findings.append(f"layer.{field}")
    env = packets.get("no_ambient_authority_packet.json")
    if isinstance(env, dict):
        if env.get("openai_api_key_present") is not False:
            findings.append("no_ambient_authority.openai_api_key_present")
        if env.get("proxy_env_present") not in ([], None):
            findings.append("no_ambient_authority.proxy_env_present")
        if env.get("browser_supplied_authority") is not False:
            findings.append("no_ambient_authority.browser_supplied_authority")
        if env.get("remote_client_supplied_authority") is not False:
            findings.append("no_ambient_authority.remote_client_supplied_authority")
    model_ref = packets.get("model_availability_reference_packet.json")
    if isinstance(model_ref, dict):
        if model_ref.get("reference_only") is not True:
            findings.append("model_availability_reference.reference_only")
        for field in (
            "model_availability_expansion_claimed",
            "model_availability_reproved_in_this_contour",
            "new_model_availability_claims_allowed",
            "native_model_availability_claimed",
        ):
            if model_ref.get(field) is not False:
                findings.append(f"model_availability_reference.{field}")
    trace = packets.get("cli_runner_route_trace_packet.json")
    if isinstance(trace, dict):
        if trace.get("route_trace_state") not in {
            "route_trace_observed",
            "request_reaches_wbp_observed",
            "route_trace_unavailable_with_reason",
            "blocked_with_reason",
        }:
            findings.append("cli_runner_route_trace.route_trace_state")
        if trace.get("exit_code_counted_as_route_proof") is not False:
            findings.append("cli_runner_route_trace.exit_code_counted_as_route_proof")
        if trace.get("responses_wire_compatibility_claimed") is not False:
            findings.append("cli_runner_route_trace.responses_wire_compatibility_claimed")
        if trace.get("codex_app_acceptance_claimed") is not False:
            findings.append("cli_runner_route_trace.codex_app_acceptance_claimed")
    response = packets.get("cli_runner_response_hash_packet.json")
    if isinstance(response, dict):
        if response.get("response_exists") is True and len(str(response.get("response_sha256") or "")) != 64:
            findings.append("cli_runner_response_hash.response_sha256")
        for field in ("raw_prompt_recorded", "auth_header_recorded", "raw_upstream_secret_recorded"):
            if response.get(field) is not False:
                findings.append(f"cli_runner_response_hash.{field}")
    claims = packets.get("cli_runner_smoke_packet.json")
    if isinstance(claims, dict):
        for field in (
            "native_app_claimed",
            "original_codex_lane_claimed",
            "response_accepted_by_codex_app",
            "model_availability_expansion_claimed",
            "model_availability_reproved_in_this_contour",
            "new_model_availability_claims_allowed",
            "streaming_claimed",
            "tool_loop_claimed",
            "direct_egress_absence_claimed",
            "final_e2e_claimed",
        ):
            if claims.get(field) is not False:
                findings.append(f"cli_runner_smoke.{field}")
    return sorted(set(findings))


def remove_tree(path: Path) -> dict[str, Any]:
    existed_before = path.exists()
    if existed_before:
        shutil.rmtree(path)
    return {
        "path": str(path),
        "existed_before": existed_before,
        "exists_after": path.exists(),
        "cleanup_performed": existed_before,
        "owned_session_root_only": True,
        "status": "passed" if not path.exists() else "failed",
    }
