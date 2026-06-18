# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .native_filesystem_probe import (
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
)
from .real_custom_codex_hook_proof import _runtime_secret_values
from .real_user_prompt_submit_ledger_proof import (
    REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
    REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
    run_real_user_prompt_submit_ledger_proof_command,
)
from .router_hook_entry import _safe_text
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import hook_ledger_path


REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND = (
    "wbp_real_custom_app_submit_ledger_proof"
)

REAL_CUSTOM_APP_SUBMIT_LEDGER_OK = "OK"
REAL_CUSTOM_APP_SUBMIT_LEDGER_LEDGER_NOT_PROVEN = (
    "WBP_REAL_CUSTOM_APP_SUBMIT_LEDGER_NOT_PROVEN"
)
REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN = (
    "WBP_REAL_CUSTOM_APP_SUBMIT_APP_NOT_PROVEN"
)
REAL_CUSTOM_APP_SUBMIT_LEDGER_STALE = "WBP_REAL_CUSTOM_APP_SUBMIT_LEDGER_STALE"
REAL_CUSTOM_APP_SUBMIT_LEDGER_UNSAFE_SOURCE = (
    "WBP_REAL_CUSTOM_APP_SUBMIT_LEDGER_UNSAFE_SOURCE"
)
REAL_CUSTOM_APP_SUBMIT_LEDGER_INVALID = "WBP_REAL_CUSTOM_APP_SUBMIT_LEDGER_INVALID"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_digest(value: object) -> str:
    return _sha256_text(
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    )


def _read_json_mapping_file(
    path: Path,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_present": path.exists(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_path_recorded": False,
        f"{prefix}_file_error_code": "",
    }
    if not path.exists():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _file_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _process_lines(process_inventory: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in ("sample", "custom_process_lines", "default_process_lines"):
        value = process_inventory.get(key)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            continue
        for item in value:
            if isinstance(item, str) and item:
                lines.append(item)
    return lines


def _process_inventory_observation(
    process_inventory: Mapping[str, Any] | None,
    *,
    process_inventory_live: bool = True,
) -> dict[str, Any]:
    inventory = _mapping(process_inventory)
    lines = _process_lines(inventory)
    wbp_root = any(
        "Codex WBP Clean.app/Contents/MacOS/Codex" in line for line in lines
    )
    wbp_server = any(
        "Codex WBP Clean.app/Contents/Resources/codex app-server" in line
        for line in lines
    )
    stock_root = any(
        "Codex.app/Contents/MacOS/Codex" in line
        and "Codex WBP Clean.app/" not in line
        for line in lines
    )
    return {
        "process_inventory_present": bool(inventory),
        "process_inventory_source_kind": (
            "live_ps" if process_inventory_live else "provided_file"
        ),
        "process_inventory_live": bool(process_inventory_live),
        "process_inventory_digest": _json_digest(
            {
                "sample": inventory.get("sample", []),
                "custom_process_lines": inventory.get("custom_process_lines", []),
                "default_process_lines": inventory.get("default_process_lines", []),
            }
        ) if inventory else "",
        "process_inventory_line_count": len(lines),
        "process_inventory_raw_lines_recorded": False,
        "wbp_clean_app_process_observed": wbp_root,
        "wbp_clean_app_server_process_observed": wbp_server,
        "stock_codex_app_process_observed": stock_root,
    }


def _ledger_required_failures(ledger_proof: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if ledger_proof.get("packet_kind") != REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND:
        failures.append("ledger_proof_packet_kind_invalid")
    if ledger_proof.get("status") != "ok":
        failures.append("ledger_proof_packet_not_ok")
    if ledger_proof.get("machine_error_code") != REAL_USER_PROMPT_SUBMIT_LEDGER_OK:
        failures.append("ledger_proof_machine_error_not_ok")
    for field, reason in (
        ("real_user_prompt_submit_ledger_proven", "real_ledger_not_proven"),
        ("custom_codex_origin_proven", "custom_codex_origin_not_proven"),
        ("native_custom_codex_flow_proven", "native_custom_codex_flow_not_proven"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_ledger_written", "hook_ledger_not_written"),
        ("hook_event_transport_stdin", "hook_event_transport_not_stdin"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("thread_or_turn_digest_bound", "thread_or_turn_digest_not_bound"),
        ("hook_ledger_file_profile_owned", "hook_ledger_not_profile_owned"),
        ("codex_hook_trusted_by_profile_state", "codex_hook_trust_state_not_proven"),
    ):
        if ledger_proof.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(ledger_proof.get("prompt_digest")):
        failures.append("ledger_prompt_digest_missing")
    return sorted(set(failures))


def _parent_process_failures(ledger_proof: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if ledger_proof.get("hook_parent_process_chain_observed") is not True:
        failures.append("hook_parent_process_chain_not_observed")
    if ledger_proof.get("hook_parent_process_chain_path_proven") is not True:
        failures.append("hook_parent_process_chain_path_not_proven")
    if ledger_proof.get("hook_parent_process_chain_exact_path_classified") is not True:
        failures.append("hook_parent_process_chain_exact_path_not_classified")
    if not _hex_sha256(ledger_proof.get("hook_parent_process_chain_digest")):
        failures.append("hook_parent_process_chain_digest_missing")
    if _safe_int(ledger_proof.get("hook_parent_process_chain_length")) <= 0:
        failures.append("hook_parent_process_chain_empty")
    if ledger_proof.get("hook_parent_process_chain_custom_wbp_clean_app") is not True:
        failures.append("hook_parent_process_chain_not_wbp_clean_app")
    if (
        ledger_proof.get(
            "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound"
        )
        is not True
    ):
        failures.append("hook_parent_process_chain_wbp_clean_app_path_not_bound")
    if ledger_proof.get("hook_parent_process_chain_app_server") is not True:
        failures.append("hook_parent_process_chain_app_server_not_observed")
    if (
        ledger_proof.get("hook_parent_process_chain_app_server_executable_path_bound")
        is not True
    ):
        failures.append("hook_parent_process_chain_app_server_path_not_bound")
    if ledger_proof.get("hook_parent_process_chain_clean_root") is not True:
        failures.append("hook_parent_process_chain_clean_root_not_observed")
    if (
        ledger_proof.get("hook_parent_process_chain_clean_root_executable_path_bound")
        is not True
    ):
        failures.append("hook_parent_process_chain_clean_root_path_not_bound")
    if ledger_proof.get("hook_parent_process_chain_stock_codex_app") is True:
        failures.append("hook_parent_process_chain_stock_codex_app")
    if ledger_proof.get("hook_parent_process_chain_command_text_substring_only") is True:
        failures.append("hook_parent_process_chain_command_text_substring_only")
    if ledger_proof.get("hook_parent_process_raw_lines_recorded") is True:
        failures.append("hook_parent_process_raw_lines_recorded")
    return sorted(set(failures))


def _process_inventory_failures(observation: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if observation.get("process_inventory_live") is not True:
        failures.append("process_inventory_not_live")
    if observation.get("process_inventory_present") is not True:
        failures.append("process_inventory_missing")
    if observation.get("wbp_clean_app_process_observed") is not True:
        failures.append("wbp_clean_app_process_not_observed")
    if observation.get("wbp_clean_app_server_process_observed") is not True:
        failures.append("wbp_clean_app_server_process_not_observed")
    if (
        observation.get("stock_codex_app_process_observed") is True
        and observation.get("wbp_clean_app_process_observed") is not True
    ):
        failures.append("stock_codex_app_without_wbp_clean_rejected")
    if observation.get("process_inventory_raw_lines_recorded") is True:
        failures.append("process_inventory_raw_lines_recorded")
    return sorted(set(failures))


def _freshness_failures(
    *,
    ledger_mtime_before_ns: int,
    ledger_mtime_after_ns: int,
) -> list[str]:
    failures: list[str] = []
    if ledger_mtime_before_ns < 0:
        failures.append("ledger_pre_submit_mtime_missing")
    if ledger_mtime_after_ns <= 0:
        failures.append("ledger_post_submit_mtime_missing")
    if ledger_mtime_before_ns >= 0 and ledger_mtime_after_ns <= ledger_mtime_before_ns:
        failures.append("hook_ledger_not_newer_than_pre_submit_snapshot")
    return failures


def _unsafe_ledger_proof_failures(ledger_proof: Mapping[str, Any]) -> list[str]:
    checks = {
        "api_lane_called": "ledger_must_not_claim_api_lane_called",
        "api_response_received": "ledger_must_not_claim_api_response_received",
        "dispatch_attempted": "ledger_must_not_claim_dispatch_attempted",
        "dispatch_proven": "ledger_must_not_claim_dispatch_proven",
        "route_bound_dispatch_proven": "ledger_must_not_claim_route_bound_dispatch",
        "provider_response_proven": "ledger_must_not_claim_provider_response",
        "handoff_file_written": "ledger_must_not_claim_handoff_file_written",
        "handoff_delivered": "ledger_must_not_claim_handoff_delivered",
        "delivery_observed": "ledger_must_not_claim_delivery_observed",
        "custom_codex_ui_visibility_proven": (
            "ledger_must_not_claim_custom_codex_ui_visibility"
        ),
        "codex_working_flow_delivery_proven": (
            "ledger_must_not_claim_codex_working_flow_delivery"
        ),
        "native_free_chat_router_proven": (
            "ledger_must_not_claim_native_free_chat_router"
        ),
        "live_provider_proven": "ledger_must_not_claim_live_provider",
        "product_ready": "ledger_must_not_claim_product_ready",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "raw_route_id_recorded": "raw_route_id_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
    }
    return sorted(
        {reason for field, reason in checks.items() if ledger_proof.get(field) is True}
    )


def _machine_error_code(
    *,
    unsafe_failures: Sequence[str],
    ledger_failures: Sequence[str],
    parent_failures: Sequence[str],
    process_failures: Sequence[str],
    freshness_failures: Sequence[str],
) -> str:
    if not (
        unsafe_failures
        or ledger_failures
        or parent_failures
        or process_failures
        or freshness_failures
    ):
        return REAL_CUSTOM_APP_SUBMIT_LEDGER_OK
    if unsafe_failures:
        return REAL_CUSTOM_APP_SUBMIT_LEDGER_UNSAFE_SOURCE
    if ledger_failures:
        return REAL_CUSTOM_APP_SUBMIT_LEDGER_LEDGER_NOT_PROVEN
    if parent_failures or process_failures:
        return REAL_CUSTOM_APP_SUBMIT_LEDGER_APP_NOT_PROVEN
    if freshness_failures:
        return REAL_CUSTOM_APP_SUBMIT_LEDGER_STALE
    return REAL_CUSTOM_APP_SUBMIT_LEDGER_INVALID


def build_real_custom_app_submit_ledger_proof_packet(
    *,
    ledger_proof_packet: Mapping[str, Any] | None,
    prompt_text: object,
    process_inventory: Mapping[str, Any] | None,
    ledger_mtime_before_ns: int,
    ledger_mtime_after_ns: int,
    ledger_file_sha256: str = "",
    runtime_context: Mapping[str, Any] | None = None,
    process_inventory_live: bool = True,
) -> dict[str, Any]:
    ledger_proof = _mapping(ledger_proof_packet)
    process_observation = _process_inventory_observation(
        process_inventory,
        process_inventory_live=process_inventory_live,
    )
    ledger_failures = _ledger_required_failures(ledger_proof)
    parent_failures = _parent_process_failures(ledger_proof)
    process_failures = _process_inventory_failures(process_observation)
    freshness = _freshness_failures(
        ledger_mtime_before_ns=ledger_mtime_before_ns,
        ledger_mtime_after_ns=ledger_mtime_after_ns,
    )
    unsafe_failures = _unsafe_ledger_proof_failures(ledger_proof)
    blocking_reasons = sorted(
        set(
            ledger_failures
            + parent_failures
            + process_failures
            + freshness
            + unsafe_failures
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        unsafe_failures=unsafe_failures,
        ledger_failures=ledger_failures,
        parent_failures=parent_failures,
        process_failures=process_failures,
        freshness_failures=freshness,
    )
    prompt_digest = _hex_sha256(ledger_proof.get("prompt_digest"))
    context = _mapping(runtime_context)
    extra = {
        **process_observation,
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "proof_scope": "real_custom_codex_app_submit_to_file_backed_ledger_gate_only",
        "app_submit_proof_scope": (
            "hook_parent_process_chain_and_current_process_inventory_digest_bound"
            if ok
            else "not_proven"
        ),
        "source_file_unforgeable": False,
        "cryptographic_app_submit_proven": False,
        "does_not_prove_source_file_unforgeable": True,
        "real_custom_app_submit_ledger_proven": ok,
        "custom_app_submit_proven": ok,
        "custom_app_submit_ledger_gate_proven": ok,
        "command_origin_surface": "custom_codex_app" if ok else "",
        "real_user_prompt_submit_ledger_proven": (
            ledger_proof.get("real_user_prompt_submit_ledger_proven") is True
        ),
        "ledger_proof_packet_kind": _safe_text(
            ledger_proof.get("packet_kind"),
            limit=96,
        ),
        "ledger_proof_status": _safe_text(ledger_proof.get("status"), limit=32),
        "ledger_proof_machine_error_code": _safe_text(
            ledger_proof.get("machine_error_code"),
            limit=96,
        ),
        "hook_prompt_digest_bound": ledger_proof.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": (
            ledger_proof.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": (
            ledger_proof.get("thread_or_turn_digest_bound") is True
        ),
        "hook_event_transport_stdin": (
            ledger_proof.get("hook_event_transport_stdin") is True
        ),
        "prompt_digest": prompt_digest,
        "hook_parent_process_chain_observed": (
            ledger_proof.get("hook_parent_process_chain_observed") is True
        ),
        "hook_parent_process_chain_path_proven": (
            ledger_proof.get("hook_parent_process_chain_path_proven") is True
        ),
        "hook_parent_process_chain_exact_path_classified": (
            ledger_proof.get("hook_parent_process_chain_exact_path_classified") is True
        ),
        "hook_parent_process_chain_digest": _hex_sha256(
            ledger_proof.get("hook_parent_process_chain_digest")
        ),
        "hook_parent_process_chain_length": _safe_int(
            ledger_proof.get("hook_parent_process_chain_length")
        ),
        "hook_parent_process_chain_custom_wbp_clean_app": (
            ledger_proof.get("hook_parent_process_chain_custom_wbp_clean_app") is True
        ),
        "hook_parent_process_chain_app_server": (
            ledger_proof.get("hook_parent_process_chain_app_server") is True
        ),
        "hook_parent_process_chain_clean_root": (
            ledger_proof.get("hook_parent_process_chain_clean_root") is True
        ),
        "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound": (
            ledger_proof.get(
                "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound"
            )
            is True
        ),
        "hook_parent_process_chain_app_server_executable_path_bound": (
            ledger_proof.get(
                "hook_parent_process_chain_app_server_executable_path_bound"
            )
            is True
        ),
        "hook_parent_process_chain_clean_root_executable_path_bound": (
            ledger_proof.get(
                "hook_parent_process_chain_clean_root_executable_path_bound"
            )
            is True
        ),
        "hook_parent_process_chain_stock_codex_app": (
            ledger_proof.get("hook_parent_process_chain_stock_codex_app") is True
        ),
        "hook_parent_process_chain_command_text_substring_only": (
            ledger_proof.get("hook_parent_process_chain_command_text_substring_only")
            is True
        ),
        "hook_parent_process_raw_lines_recorded": (
            ledger_proof.get("hook_parent_process_raw_lines_recorded") is True
        ),
        "ledger_mtime_before_ns": max(-1, int(ledger_mtime_before_ns)),
        "ledger_mtime_after_ns": max(0, int(ledger_mtime_after_ns)),
        "ledger_newer_than_pre_submit_snapshot": (
            ledger_mtime_before_ns >= 0
            and ledger_mtime_after_ns > ledger_mtime_before_ns
        ),
        "ledger_file_sha256": _hex_sha256(ledger_file_sha256),
        "ledger_required_failures": ledger_failures,
        "parent_process_failures": parent_failures,
        "process_inventory_failures": process_failures,
        "freshness_failures": freshness,
        "unsafe_source_failures": unsafe_failures,
        "api_lane_called": False,
        "api_response_received": False,
        "dispatch_attempted": False,
        "dispatch_status": "not_attempted",
        "dispatch_proven": False,
        "route_bound_dispatch_proven": False,
        "provider_response_proven": False,
        "controlled_provider_response_proven": False,
        "handoff_file_written": False,
        "handoff_delivered": False,
        "delivery_observed": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "live_provider_proven": False,
        "live_provider_response_proven": False,
        "external_live_provider_response_proven": False,
        "product_ready": False,
        "does_not_prove_dispatch": True,
        "does_not_prove_handoff": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_live_provider": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a real Custom Codex app submit reached the hook ledger."
            if ok
            else "WBP blocked Custom Codex app submit ledger proof."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[str(prompt_text or ""), *_runtime_secret_values(context)],
        extra=extra,
    )


def run_real_custom_app_submit_ledger_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    ledger_mtime_before_ns: int,
    hook_ledger_file: str | None = None,
    runtime_context_file: str | None = None,
    process_inventory_file: str | None = None,
    custom_user_data_dir: str | None = None,
) -> dict[str, Any]:
    ledger_path = (
        Path(hook_ledger_file).expanduser()
        if hook_ledger_file
        else hook_ledger_path(paths)
    )
    ledger_proof = run_real_user_prompt_submit_ledger_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        hook_ledger_file=str(ledger_path),
        runtime_context_file=runtime_context_file,
    )
    if process_inventory_file:
        process_inventory, process_metadata = _read_json_mapping_file(
            Path(process_inventory_file).expanduser(),
            prefix="process_inventory",
        )
        if process_metadata.get("process_inventory_file_mapping") is not True:
            process_inventory = {}
        process_inventory_live = False
    else:
        profile_paths = default_persistent_custom_profile_paths()
        process_inventory = collect_codex_process_inventory(
            custom_user_data_dir=custom_user_data_dir
            or str(profile_paths["user_data_dir"])
        )
        process_inventory_live = True
    return build_real_custom_app_submit_ledger_proof_packet(
        ledger_proof_packet=ledger_proof,
        prompt_text=prompt_text,
        process_inventory=process_inventory,
        ledger_mtime_before_ns=ledger_mtime_before_ns,
        ledger_mtime_after_ns=_file_mtime_ns(ledger_path),
        ledger_file_sha256=_file_sha256(ledger_path),
        process_inventory_live=process_inventory_live,
    )
