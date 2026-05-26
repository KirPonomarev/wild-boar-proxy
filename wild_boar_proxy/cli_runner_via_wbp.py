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
            "model_availability_expansion",
            "streaming_compatibility",
            "tool_loop_compatibility",
            "full_responses_wire_compatibility",
            "final_e2e",
        ],
        "native_app_claimed": False,
        "original_codex_lane_claimed": False,
        "model_availability_reproof_claimed": False,
        "streaming_claimed": False,
        "tool_loop_claimed": False,
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
    return {
        "contour_id": CONTOUR_ID,
        "status": "passed" if passed else "failed",
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
        and model_id == PRIMARY_MODEL_ID
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
        "selected_model_id": model_id,
        "model_claim_level": (
            "gpt-5.4-mini_cli_runner_non_stream_wbp_200_proven"
            if passed
            else "unproven"
        ),
        "model_availability_expansion_claimed": False,
        "response_match_observed": response_match_observed,
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
