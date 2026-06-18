# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import plistlib
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .native_filesystem_probe import default_persistent_custom_profile_paths
from .real_custom_app_submit_ledger_proof import (
    REAL_CUSTOM_APP_SUBMIT_LEDGER_OK,
    REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND,
    run_real_custom_app_submit_ledger_proof_command,
)
from .router_hook_entry import _safe_text
from .runtime import RuntimePaths


CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND = "wbp_custom_ui_origin_admission"

CUSTOM_UI_ORIGIN_ADMISSION_OK = "OK"
CUSTOM_UI_ORIGIN_ADMISSION_BUNDLE_ID_COLLISION = (
    "WBP_CUSTOM_UI_ORIGIN_BUNDLE_ID_COLLISION"
)
CUSTOM_UI_ORIGIN_ADMISSION_LEDGER_NOT_PROVEN = (
    "WBP_CUSTOM_UI_ORIGIN_LEDGER_NOT_PROVEN"
)
CUSTOM_UI_ORIGIN_ADMISSION_UNSAFE_SOURCE = "WBP_CUSTOM_UI_ORIGIN_UNSAFE_SOURCE"
CUSTOM_UI_ORIGIN_ADMISSION_NOT_PROVEN = "WBP_CUSTOM_UI_ORIGIN_NOT_PROVEN"
CUSTOM_UI_ORIGIN_ADMISSION_INVALID = "WBP_CUSTOM_UI_ORIGIN_INVALID"


def default_stock_codex_app_path() -> Path:
    return Path("/Applications/Codex.app")


def default_custom_codex_app_path() -> Path:
    return Path.home() / "Applications" / "Codex WBP Clean.app"


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_bundle_identifier(app_path: Path, *, prefix: str) -> dict[str, Any]:
    app = app_path.expanduser()
    plist_path = app / "Contents" / "Info.plist"
    metadata: dict[str, Any] = {
        f"{prefix}_app_present": app.exists(),
        f"{prefix}_info_plist_present": plist_path.exists(),
        f"{prefix}_info_plist_read": False,
        f"{prefix}_bundle_id": "",
        f"{prefix}_bundle_id_present": False,
        f"{prefix}_bundle_read_error_code": "",
        f"{prefix}_app_path_recorded": False,
        f"{prefix}_info_plist_path_recorded": False,
    }
    if not plist_path.exists():
        metadata[f"{prefix}_bundle_read_error_code"] = "info_plist_missing"
        return metadata
    try:
        with plist_path.open("rb") as handle:
            parsed = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        metadata[f"{prefix}_bundle_read_error_code"] = "info_plist_invalid"
        return metadata
    metadata[f"{prefix}_info_plist_read"] = True
    bundle_id = _safe_text(parsed.get("CFBundleIdentifier"), limit=128)
    metadata[f"{prefix}_bundle_id"] = bundle_id
    metadata[f"{prefix}_bundle_id_present"] = bool(bundle_id)
    if not bundle_id:
        metadata[f"{prefix}_bundle_read_error_code"] = "bundle_id_missing"
    return metadata


def _path_declared(path: Path | str | None) -> bool:
    return bool(_safe_text(str(path or ""), limit=512))


def _path_present(path: Path | str | None) -> bool:
    if not _path_declared(path):
        return False
    try:
        return Path(str(path)).expanduser().exists()
    except OSError:
        return False


def _safe_reason_tokens(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _unsafe_submit_packet_failures(packet: Mapping[str, Any]) -> list[str]:
    checks = {
        "api_lane_called": "custom_app_submit_must_not_claim_api_lane_called",
        "api_response_received": "custom_app_submit_must_not_claim_api_response",
        "dispatch_attempted": "custom_app_submit_must_not_claim_dispatch",
        "dispatch_proven": "custom_app_submit_must_not_claim_dispatch",
        "route_bound_dispatch_proven": (
            "custom_app_submit_must_not_claim_route_bound_dispatch"
        ),
        "provider_response_proven": (
            "custom_app_submit_must_not_claim_provider_response"
        ),
        "handoff_file_written": "custom_app_submit_must_not_claim_handoff",
        "handoff_delivered": "custom_app_submit_must_not_claim_handoff",
        "delivery_observed": "custom_app_submit_must_not_claim_delivery",
        "custom_codex_ui_visibility_proven": (
            "custom_app_submit_must_not_claim_custom_codex_ui_visibility"
        ),
        "codex_working_flow_delivery_proven": (
            "custom_app_submit_must_not_claim_working_flow_delivery"
        ),
        "native_free_chat_router_proven": (
            "custom_app_submit_must_not_claim_native_router"
        ),
        "live_provider_proven": "custom_app_submit_must_not_claim_live_provider",
        "product_ready": "custom_app_submit_must_not_claim_product_ready",
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
        {reason for field, reason in checks.items() if packet.get(field) is True}
    )


def _submit_packet_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != REAL_CUSTOM_APP_SUBMIT_LEDGER_PROOF_PACKET_KIND:
        failures.append("custom_app_submit_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("custom_app_submit_packet_not_ok")
    if packet.get("machine_error_code") != REAL_CUSTOM_APP_SUBMIT_LEDGER_OK:
        failures.append("custom_app_submit_machine_error_not_ok")
    if packet.get("real_custom_app_submit_ledger_proven") is not True:
        failures.append("real_custom_app_submit_ledger_not_proven")
    if packet.get("custom_app_submit_proven") is not True:
        failures.append("custom_app_submit_not_proven")
    if packet.get("custom_app_submit_ledger_gate_proven") is not True:
        failures.append("custom_app_submit_ledger_gate_not_proven")
    if packet.get("real_user_prompt_submit_ledger_proven") is not True:
        failures.append("real_user_prompt_submit_ledger_not_proven")
    if packet.get("hook_prompt_digest_bound") is not True:
        failures.append("hook_prompt_digest_not_bound")
    if packet.get("hook_runtime_context_digest_bound") is not True:
        failures.append("hook_runtime_context_digest_not_bound")
    if packet.get("thread_or_turn_digest_bound") is not True:
        failures.append("thread_or_turn_digest_not_bound")
    if packet.get("ledger_newer_than_pre_submit_snapshot") is not True:
        failures.append("fresh_user_prompt_submit_ledger_not_proven")
    if packet.get("process_inventory_live") is not True:
        failures.append("custom_process_inventory_not_live")
    if packet.get("wbp_clean_app_process_observed") is not True:
        failures.append("wbp_clean_app_process_not_observed")
    if packet.get("wbp_clean_app_server_process_observed") is not True:
        failures.append("wbp_clean_app_server_process_not_observed")
    return sorted(set(failures))


def _machine_error_code(
    *,
    blocking_reasons: list[str],
    unsafe_failures: list[str],
    bundle_id_collision_detected: bool,
    submit_failures: list[str],
) -> str:
    if not blocking_reasons:
        return CUSTOM_UI_ORIGIN_ADMISSION_OK
    if unsafe_failures:
        return CUSTOM_UI_ORIGIN_ADMISSION_UNSAFE_SOURCE
    if bundle_id_collision_detected:
        return CUSTOM_UI_ORIGIN_ADMISSION_BUNDLE_ID_COLLISION
    if any(reason.endswith("_missing") for reason in blocking_reasons):
        return CUSTOM_UI_ORIGIN_ADMISSION_INVALID
    if submit_failures:
        return CUSTOM_UI_ORIGIN_ADMISSION_LEDGER_NOT_PROVEN
    return CUSTOM_UI_ORIGIN_ADMISSION_NOT_PROVEN


def build_custom_ui_origin_admission_packet(
    *,
    custom_app_submit_packet: Mapping[str, Any] | None,
    prompt_text: object,
    stock_app_path: Path | str,
    custom_app_path: Path | str,
    custom_profile_dir: Path | str | None,
    custom_user_data_dir: Path | str | None,
    custom_launcher_path: Path | str | None,
) -> dict[str, Any]:
    submit_packet = _mapping(custom_app_submit_packet)
    stock_bundle = _read_bundle_identifier(Path(str(stock_app_path)), prefix="stock_codex")
    custom_bundle = _read_bundle_identifier(Path(str(custom_app_path)), prefix="custom_codex")

    stock_bundle_id = stock_bundle["stock_codex_bundle_id"]
    custom_bundle_id = custom_bundle["custom_codex_bundle_id"]
    bundle_id_collision_detected = (
        bool(stock_bundle_id)
        and bool(custom_bundle_id)
        and stock_bundle_id == custom_bundle_id
    )
    custom_app_identity_distinct = (
        bool(stock_bundle_id)
        and bool(custom_bundle_id)
        and stock_bundle_id != custom_bundle_id
    )

    custom_profile_dir_declared = _path_declared(custom_profile_dir)
    custom_user_data_dir_declared = _path_declared(custom_user_data_dir)
    custom_launcher_declared = _path_declared(custom_launcher_path)

    identity_failures: list[str] = []
    if stock_bundle.get("stock_codex_bundle_id_present") is not True:
        identity_failures.append("stock_codex_bundle_id_missing")
    if custom_bundle.get("custom_codex_bundle_id_present") is not True:
        identity_failures.append("custom_codex_bundle_id_missing")
    if bundle_id_collision_detected:
        identity_failures.append("bundle_id_collision_detected")
    if not custom_profile_dir_declared:
        identity_failures.append("custom_profile_dir_missing")
    if not custom_user_data_dir_declared:
        identity_failures.append("custom_user_data_dir_missing")
    if not custom_launcher_declared:
        identity_failures.append("custom_launcher_missing")

    unsafe_failures = _unsafe_submit_packet_failures(submit_packet)
    submit_failures = _submit_packet_failures(submit_packet)
    fresh_user_prompt_submit_ledger_proven = not submit_failures
    prompt_digest = _hex_sha256(submit_packet.get("prompt_digest"))

    custom_instance_coexistence_possible = (
        custom_app_identity_distinct
        and custom_profile_dir_declared
        and custom_user_data_dir_declared
        and custom_launcher_declared
    )
    custom_instance_coexistence_proven = (
        custom_instance_coexistence_possible
        and fresh_user_prompt_submit_ledger_proven
        and submit_packet.get("process_inventory_live") is True
        and submit_packet.get("wbp_clean_app_process_observed") is True
        and submit_packet.get("wbp_clean_app_server_process_observed") is True
    )
    if not custom_instance_coexistence_possible:
        identity_failures.append("custom_instance_coexistence_not_possible")
    if not custom_instance_coexistence_proven:
        identity_failures.append("custom_instance_coexistence_not_proven")

    blocking_reasons = sorted(set(identity_failures + unsafe_failures + submit_failures))
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        blocking_reasons=blocking_reasons,
        unsafe_failures=unsafe_failures,
        bundle_id_collision_detected=bundle_id_collision_detected,
        submit_failures=submit_failures,
    )

    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_UI_ORIGIN_ADMISSION_PACKET_KIND,
        "proof_scope": "custom_codex_ui_origin_admission_gate_only",
        **stock_bundle,
        **custom_bundle,
        "bundle_id_collision_detected": bundle_id_collision_detected,
        "custom_app_identity_distinct": custom_app_identity_distinct,
        "custom_app_path_recorded": False,
        "stock_app_path_recorded": False,
        "custom_profile_dir_declared": custom_profile_dir_declared,
        "custom_profile_dir_present": _path_present(custom_profile_dir),
        "custom_profile_dir_path_recorded": False,
        "custom_user_data_dir_declared": custom_user_data_dir_declared,
        "custom_user_data_dir_present": _path_present(custom_user_data_dir),
        "custom_user_data_dir_path_recorded": False,
        "custom_launcher_declared": custom_launcher_declared,
        "custom_launcher_present": _path_present(custom_launcher_path),
        "custom_launcher_path_recorded": False,
        "custom_instance_coexistence_possible": custom_instance_coexistence_possible,
        "custom_instance_coexistence_proven": custom_instance_coexistence_proven,
        "fresh_user_prompt_submit_ledger_proven": (
            fresh_user_prompt_submit_ledger_proven
        ),
        "prompt_digest": prompt_digest,
        "prompt_digest_present": bool(prompt_digest),
        "custom_ui_origin_admitted": ok,
        "custom_codex_flow_origin_admitted": ok,
        "real_custom_app_submit_ledger_proven": (
            submit_packet.get("real_custom_app_submit_ledger_proven") is True
        ),
        "custom_app_submit_proven": (
            submit_packet.get("custom_app_submit_proven") is True
        ),
        "custom_app_submit_ledger_gate_proven": (
            submit_packet.get("custom_app_submit_ledger_gate_proven") is True
        ),
        "real_user_prompt_submit_ledger_proven": (
            submit_packet.get("real_user_prompt_submit_ledger_proven") is True
        ),
        "hook_prompt_digest_bound": (
            submit_packet.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": (
            submit_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": (
            submit_packet.get("thread_or_turn_digest_bound") is True
        ),
        "process_inventory_live": submit_packet.get("process_inventory_live") is True,
        "wbp_clean_app_process_observed": (
            submit_packet.get("wbp_clean_app_process_observed") is True
        ),
        "wbp_clean_app_server_process_observed": (
            submit_packet.get("wbp_clean_app_server_process_observed") is True
        ),
        "stock_codex_app_process_observed": (
            submit_packet.get("stock_codex_app_process_observed") is True
        ),
        "custom_app_submit_packet_kind": _safe_text(
            submit_packet.get("packet_kind"),
            limit=96,
        ),
        "custom_app_submit_status": _safe_text(
            submit_packet.get("status"),
            limit=32,
        ),
        "custom_app_submit_machine_error_code": _safe_text(
            submit_packet.get("machine_error_code"),
            limit=96,
        ),
        "custom_app_submit_blocking_reasons": sorted(
            _safe_reason_tokens(submit_packet.get("blocking_reasons"))
        ),
        "custom_app_submit_required_failures": submit_failures,
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
        "does_not_prove_custom_codex_ui_visibility": True,
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
            "WBP admitted Custom Codex UI origin for the fresh hook ledger."
            if ok
            else "WBP blocked Custom Codex UI origin admission."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=[str(prompt_text or "")],
        extra=extra,
    )


def run_custom_ui_origin_admission_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    ledger_mtime_before_ns: int,
    hook_ledger_file: str | None = None,
    runtime_context_file: str | None = None,
    process_inventory_file: str | None = None,
    stock_app_path: str | None = None,
    custom_app_path: str | None = None,
    custom_profile_dir: str | None = None,
    custom_user_data_dir: str | None = None,
    custom_launcher_path: str | None = None,
) -> dict[str, Any]:
    profile_paths = default_persistent_custom_profile_paths()
    submit_packet = run_real_custom_app_submit_ledger_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        ledger_mtime_before_ns=ledger_mtime_before_ns,
        hook_ledger_file=hook_ledger_file,
        runtime_context_file=runtime_context_file,
        process_inventory_file=process_inventory_file,
        custom_user_data_dir=(
            custom_user_data_dir or profile_paths.get("user_data_dir", "")
        ),
    )
    return build_custom_ui_origin_admission_packet(
        custom_app_submit_packet=submit_packet,
        prompt_text=prompt_text,
        stock_app_path=stock_app_path or default_stock_codex_app_path(),
        custom_app_path=custom_app_path or default_custom_codex_app_path(),
        custom_profile_dir=(
            custom_profile_dir or profile_paths.get("persistent_profile_root", "")
        ),
        custom_user_data_dir=(
            custom_user_data_dir or profile_paths.get("user_data_dir", "")
        ),
        custom_launcher_path=(
            custom_launcher_path or profile_paths.get("launcher_path", "")
        ),
    )
