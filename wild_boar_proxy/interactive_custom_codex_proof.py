# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .core import packets
from .custom_codex_admission import (
    _input_hashes_digest,
    _routes_file_contains_any_route,
    _select_external_models_dir,
)
from .external_models import run_external_models_command
from .proof_seal import (
    sha256_file,
    run_proof_seal_create_command,
    run_proof_seal_verify_command,
)
from .real_custom_codex_hook_proof import (
    REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    runtime_context_digest,
    run_real_custom_codex_hook_proof_command,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths, write_json_atomic
from .user_prompt_submit_hook_producer import (
    build_user_prompt_submit_readiness_packet,
    hook_ledger_path,
)


INTERACTIVE_PREFLIGHT_PACKET_KIND = "wbp_interactive_custom_codex_preflight"
INTERACTIVE_COLLECT_PACKET_KIND = "wbp_interactive_custom_codex_proof"

INTERACTIVE_OK = "OK"
INTERACTIVE_PREFLIGHT_NOT_READY = "WBP_INTERACTIVE_CUSTOM_CODEX_PREFLIGHT_NOT_READY"
INTERACTIVE_PREFLIGHT_INVALID = "WBP_INTERACTIVE_CUSTOM_CODEX_PREFLIGHT_INVALID"
INTERACTIVE_HOOK_LEDGER_NOT_FRESH = (
    "WBP_INTERACTIVE_CUSTOM_CODEX_HOOK_LEDGER_NOT_FRESH"
)
INTERACTIVE_HOOK_PROOF_FAILED = "WBP_INTERACTIVE_CUSTOM_CODEX_HOOK_PROOF_FAILED"
INTERACTIVE_LIVE_PROVIDER_FAILED = "WBP_INTERACTIVE_CUSTOM_CODEX_LIVE_PROVIDER_FAILED"
INTERACTIVE_SEAL_FAILED = "WBP_INTERACTIVE_CUSTOM_CODEX_SEAL_FAILED"
INTERACTIVE_UNSAFE_PACKET = "WBP_INTERACTIVE_CUSTOM_CODEX_UNSAFE_PACKET"

DEFAULT_EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"
INTERACTIVE_PREFLIGHT_SURFACE = "wild-boar-proxy codex-runner interactive-preflight"
INTERACTIVE_COLLECT_SURFACE = "wild-boar-proxy codex-runner interactive-collect"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _proof_dir(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "router-hook" / "interactive-proof" / stamp


def _read_json_mapping(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = {
        "file_present": path.exists(),
        "file_read": False,
        "file_valid_json": False,
        "file_mapping": False,
        "file_path_recorded": False,
        "file_error_code": "",
    }
    if not path.exists():
        metadata["file_error_code"] = "file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["file_error_code"] = "file_invalid"
        return {}, metadata
    metadata["file_read"] = True
    metadata["file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["file_error_code"] = "file_not_mapping"
        return {}, metadata
    metadata["file_mapping"] = True
    return dict(parsed), metadata


def _runtime_secret_values(runtime_context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    allowed = runtime_context.get("allowed_api_route_ids")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        values.extend(route for route in allowed if isinstance(route, str) and route)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(route for route in routes.values() if isinstance(route, str) and route)
    return sorted(set(values))


def _write_packet(path: Path, packet: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(packet))
    return str(path)


def _preflight_packet_path(proof_root: Path) -> Path:
    return proof_root / "interactive-preflight.packet.json"


def _live_provider_packet_path(proof_root: Path) -> Path:
    return proof_root / "interactive-live-provider.packet.json"


def _source_packet_path(proof_root: Path) -> Path:
    return proof_root / "interactive-user-prompt-submit-proof.packet.json"


def _source_seal_path(proof_root: Path) -> Path:
    return proof_root / "interactive-user-prompt-submit-proof.seal.json"


def _source_seal_verify_path(proof_root: Path) -> Path:
    return proof_root / "interactive-user-prompt-submit-proof.seal-verify.packet.json"


def _final_packet_path(proof_root: Path) -> Path:
    return proof_root / "interactive-custom-codex-proof.packet.json"


def _selected_route_from_prompt(
    *,
    prompt_text: str,
    runtime_context: Mapping[str, Any],
    secret_values: Sequence[str],
) -> tuple[str, dict[str, Any]]:
    # Keep route selection in process memory; final packets record only digests
    # and booleans. Passing route ids as secret_values here would redact the
    # route before we can verify the server-owned registry.
    entry = build_router_hook_entry_packet(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
    )
    if entry.get("status") != "ok" or entry.get("route_id_allowed") is not True:
        return "", entry
    return _safe_text(entry.get("route_candidate"), limit=160), entry


def _live_provider_prompt(expected_text: str) -> str:
    return f"Answer exactly one line: {expected_text}"


def _run_live_provider_packet(
    *,
    paths: RuntimePaths,
    runtime_context: Mapping[str, Any],
    prompt_text: str,
    expected_text: str,
    proof_root: Path,
) -> tuple[dict[str, Any], str, str]:
    secret_values = [prompt_text, expected_text] + _runtime_secret_values(runtime_context)
    route_id, entry_packet = _selected_route_from_prompt(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        secret_values=secret_values,
    )
    if not route_id:
        return (
            packets.build_command_packet(
                ok=False,
                human_message="WBP blocked interactive live provider check before route selection.",
                machine_error_code=INTERACTIVE_LIVE_PROVIDER_FAILED,
                liveness="not_applicable",
                severity="recoverable",
                operator_action="stop",
                changed_files=[],
                effect=EFFECT_PROBE,
                secret_values=secret_values,
                extra={
                    "schema_version": 1,
                    "packet_kind": "wbp_interactive_live_provider_extract",
                    "router_entry_status": _safe_text(entry_packet.get("status"), limit=32),
                    "router_entry_machine_error_code": _safe_text(
                        entry_packet.get("machine_error_code"),
                        limit=96,
                    ),
                    "live_provider_packet_observed": False,
                    "route_id_allowed": False,
                    "raw_route_id_recorded": False,
                    "raw_prompt_recorded": False,
                    "raw_provider_response_recorded": False,
                    "secret_value_exposed": False,
                    "product_ready": False,
                    "blocking_reasons": ["interactive_route_not_selected"],
                },
            ),
            "",
            "",
        )
    external_models_dir, external_models_dir_source = _select_external_models_dir(
        paths,
        runtime_context,
    )
    old_external_models_dir = os.environ.get("WBP_EXTERNAL_MODELS_DIR")
    os.environ["WBP_EXTERNAL_MODELS_DIR"] = str(external_models_dir)
    try:
        packet = run_external_models_command(
            SimpleNamespace(
                external_models_command="live-format-check",
                route=route_id,
                prompt=_live_provider_prompt(expected_text),
                expected_text=expected_text,
            )
        )
    finally:
        if old_external_models_dir is None:
            os.environ.pop("WBP_EXTERNAL_MODELS_DIR", None)
        else:
            os.environ["WBP_EXTERNAL_MODELS_DIR"] = old_external_models_dir
    _write_packet(_live_provider_packet_path(proof_root), packet)
    return packet, route_id, external_models_dir_source


def _blocked_live_provider_packet(reason: str) -> dict[str, Any]:
    return packets.build_command_packet(
        ok=False,
        human_message="WBP did not call the live provider because interactive hook evidence was not admitted.",
        machine_error_code=INTERACTIVE_LIVE_PROVIDER_FAILED,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra={
            "schema_version": 1,
            "packet_kind": "wbp_interactive_live_provider_extract",
            "live_provider_packet_observed": False,
            "live_provider_call_suppressed": True,
            "live_provider_call_suppressed_reason": _safe_text(reason, limit=120),
            "api_lane_called": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "native_codex_subagent_used_as_dip": False,
            "product_ready": False,
            "raw_prompt_recorded": False,
            "raw_route_id_recorded": False,
            "raw_provider_response_recorded": False,
            "secret_value_exposed": False,
            "blocking_reasons": [reason],
        },
    )


def _read_live_provider_packet(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet, metadata = _read_json_mapping(path)
    return packet, {
        key.replace("file_", "live_provider_proof_file_"): value
        for key, value in metadata.items()
    }


def _read_preflight_packet(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    packet, metadata = _read_json_mapping(path)
    return packet, {
        key.replace("file_", "preflight_packet_file_"): value
        for key, value in metadata.items()
    }


def _read_hook_ledger(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger, metadata = _read_json_mapping(path)
    return ledger, {
        key.replace("file_", "hook_ledger_file_"): value
        for key, value in metadata.items()
    }


def _file_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _ledger_freshness_failures(
    *,
    ledger: Mapping[str, Any],
    ledger_metadata: Mapping[str, Any],
    preflight_packet: Mapping[str, Any],
    prompt_digest: str,
    context_digest: str,
    ledger_path: Path,
) -> list[str]:
    failures: list[str] = []
    if ledger_metadata.get("hook_ledger_file_present") is not True:
        failures.append("hook_ledger_missing")
    if ledger_metadata.get("hook_ledger_file_read") is not True:
        failures.append("hook_ledger_not_read")
    if ledger_metadata.get("hook_ledger_file_valid_json") is not True:
        failures.append("hook_ledger_json_invalid")
    if ledger_metadata.get("hook_ledger_file_mapping") is not True:
        failures.append("hook_ledger_not_mapping")
    if ledger.get("user_prompt_submit_hook_ran") is not True:
        failures.append("user_prompt_submit_hook_not_run")
    if ledger.get("hook_ledger_written") is not True:
        failures.append("hook_ledger_not_written")
    if ledger.get("hook_trusted") is not True:
        failures.append("hook_not_trusted_by_codex_flow")
    if ledger.get("hook_producer_state") != "HOOK_RAN_CUSTOM_CODEX_PROVEN":
        failures.append("hook_producer_state_not_custom_codex_proven")
    if _safe_text(ledger.get("prompt_digest"), limit=80) != prompt_digest:
        failures.append("hook_prompt_digest_mismatch")
    if _safe_text(ledger.get("runtime_context_digest"), limit=80) != context_digest:
        failures.append("hook_runtime_context_digest_mismatch")
    preflight_cleared_at = int(preflight_packet.get("ledger_cleared_at_unix_ns") or 0)
    if not preflight_cleared_at:
        failures.append("preflight_ledger_clear_time_missing")
    elif _file_mtime_ns(ledger_path) <= preflight_cleared_at:
        failures.append("hook_ledger_not_newer_than_preflight")
    expected_hook_digest = _safe_text(
        preflight_packet.get("expected_hook_definition_sha256"),
        limit=80,
    )
    if expected_hook_digest:
        if _safe_text(ledger.get("trusted_hook_config_sha256"), limit=80) != expected_hook_digest:
            failures.append("trusted_hook_config_digest_mismatch")
        if _safe_text(ledger.get("loaded_hook_config_sha256"), limit=80) != expected_hook_digest:
            failures.append("loaded_hook_config_digest_mismatch")
    if ledger.get("custom_codex_ui_visibility_proven") is True:
        failures.append("ledger_custom_codex_ui_claim_forbidden")
    if ledger.get("native_free_chat_router_proven") is True:
        failures.append("ledger_native_router_claim_forbidden")
    if ledger.get("product_ready") is True:
        failures.append("ledger_product_ready_claim_forbidden")
    if ledger.get("fallback_used") is True:
        failures.append("ledger_fallback_used")
    if ledger.get("local_imitation_used") is True:
        failures.append("ledger_local_imitation_used")
    if ledger.get("native_codex_subagent_used_as_dip") is True:
        failures.append("ledger_native_codex_subagent_used_as_dip")
    return sorted(set(failures))


def _create_and_verify_source_seal(
    *,
    source_packet_path: Path,
    source_seal_path: Path,
    runtime_context_digest_value: str,
    hook_ledger_digest: str,
    profile_hook_config_digest: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    create_packet = run_proof_seal_create_command(
        packet_file=str(source_packet_path),
        seal_file=str(source_seal_path),
        producer_kind="wbp_interactive_custom_codex_proof_collector",
        producer_command_digest=_sha256_text(
            "interactive-custom-codex-proof:user-prompt-submit-proof:v1"
        ),
        producer_inputs_digest=_input_hashes_digest({}),
        input_packet_files=[],
        runtime_context_digest=runtime_context_digest_value,
        hook_ledger_digest=hook_ledger_digest,
        profile_hook_config_digest=profile_hook_config_digest,
        git_commit_sha="",
    )
    verify_packet = run_proof_seal_verify_command(
        packet_file=str(source_packet_path),
        seal_file=str(source_seal_path),
        expected_packet_kind=REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
    )
    changed_files = list(create_packet.get("changed_files", []))
    return create_packet, verify_packet, changed_files


def run_interactive_custom_codex_preflight_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    proof_dir: str | None = None,
    probe_codex_app_server: bool = True,
) -> dict[str, Any]:
    proof_root = _proof_dir(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    prompt = str(prompt_text)
    context_file = runtime_context_path(paths=paths, runtime_context_file=None)
    runtime_context, context_metadata = load_runtime_context_packet(context_file)
    readiness_packet = build_user_prompt_submit_readiness_packet(
        paths=paths,
        probe_codex_app_server=probe_codex_app_server,
    )
    ledger_path = hook_ledger_path(paths)
    ledger_before_present = ledger_path.exists()
    ledger_before_sha256 = sha256_file(ledger_path) if ledger_before_present else ""
    ledger_cleared = False
    ledger_clear_error = ""
    try:
        ledger_path.unlink(missing_ok=True)
        ledger_cleared = True
    except OSError as exc:
        ledger_clear_error = type(exc).__name__
    ledger_cleared_at = int(_file_mtime_ns(ledger_path) or 0)
    if ledger_cleared:
        ledger_cleared_at = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)

    secret_values = [prompt] + _runtime_secret_values(runtime_context)
    route_id, entry_packet = _selected_route_from_prompt(
        prompt_text=prompt,
        runtime_context=runtime_context,
        secret_values=secret_values,
    )
    external_models_dir, external_models_dir_source = _select_external_models_dir(
        paths,
        runtime_context,
    )
    route_registry_selected = bool(
        route_id
        and _routes_file_contains_any_route(
            external_models_dir / "routes.json",
            {route_id},
        )
    )
    hook_config_bound = readiness_packet.get("hook_config_digest_bound") is True
    hook_script_ready = readiness_packet.get("hook_command_path_resolves") is True
    context_ready = context_metadata.get("runtime_context_file_read") is True
    prompt_route_ready = bool(entry_packet.get("status") == "ok" and route_id)
    ok = bool(
        ledger_cleared
        and not ledger_clear_error
        and context_ready
        and hook_config_bound
        and hook_script_ready
        and prompt_route_ready
        and route_registry_selected
    )
    blocking_reasons: list[str] = []
    if not ledger_cleared or ledger_clear_error:
        blocking_reasons.append("hook_ledger_clear_failed")
    if not context_ready:
        blocking_reasons.append("runtime_context_not_ready")
    if not hook_config_bound:
        blocking_reasons.append("hook_config_digest_not_bound")
    if not hook_script_ready:
        blocking_reasons.append("hook_script_not_ready")
    if not prompt_route_ready:
        blocking_reasons.append("prompt_alias_route_not_ready")
    if not route_registry_selected:
        blocking_reasons.append("external_models_route_registry_not_selected")

    changed_files = [str(_preflight_packet_path(proof_root))]
    if ledger_before_present and ledger_cleared:
        changed_files.append(str(ledger_path))
    extra = {
        **context_metadata,
        "schema_version": 1,
        "packet_kind": INTERACTIVE_PREFLIGHT_PACKET_KIND,
        "runner_launch_surface": INTERACTIVE_PREFLIGHT_SURFACE,
        "preflight_ready_for_operator_prompt": ok,
        "interactive_custom_codex_flow_proven": False,
        "hook_trust_must_be_confirmed_by_fresh_ledger": True,
        "hook_trusted": False,
        "hook_readiness_packet_status": _safe_text(
            readiness_packet.get("status"),
            limit=32,
        ),
        "hook_readiness_machine_error_code": _safe_text(
            readiness_packet.get("machine_error_code"),
            limit=96,
        ),
        "hook_config_present": readiness_packet.get("hook_config_present") is True,
        "hook_config_digest_bound": hook_config_bound,
        "hook_command_path_resolves": hook_script_ready,
        "expected_hook_definition_sha256": _safe_text(
            readiness_packet.get("expected_hook_definition_sha256"),
            limit=80,
        ),
        "prompt_digest": _sha256_text(prompt),
        "prompt_recorded": False,
        "runtime_context_digest": runtime_context_digest(runtime_context),
        "runtime_context_bound": context_ready,
        "alias_context_read": entry_packet.get("alias_context_read") is True,
        "route_id_allowed": entry_packet.get("route_id_allowed") is True,
        "allowed_api_route_ids_enforced": (
            entry_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "route_selected_for_live_check": bool(route_id),
        "route_id_recorded": False,
        "route_id_sha256": _sha256_text(route_id) if route_id else "",
        "external_models_dir_source": _safe_text(external_models_dir_source, limit=80),
        "external_models_dir_path_recorded": False,
        "external_models_dir_route_registry_selected": route_registry_selected,
        "ledger_before_present": ledger_before_present,
        "ledger_before_sha256": ledger_before_sha256,
        "ledger_cleared_before_prompt": ledger_cleared,
        "ledger_cleared_at_unix_ns": ledger_cleared_at,
        "ledger_clear_error": ledger_clear_error,
        "proof_dir_path_recorded": False,
        "declared_write_surfaces": ["proof_dir", "custom_profile_hook_ledger"],
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_product_ready": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "secret_value_exposed": False,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "changed_files": sorted(set(changed_files)),
    }
    packet = packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP prepared interactive Custom Codex proof preflight; operator prompt is required."
            if ok
            else "WBP blocked interactive Custom Codex preflight before operator prompt."
        ),
        machine_error_code=INTERACTIVE_OK if ok else INTERACTIVE_PREFLIGHT_NOT_READY,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="user_action" if ok else "stop",
        changed_files=sorted(set(changed_files)),
        effect=EFFECT_MUTATE,
        secret_values=secret_values,
        extra=extra,
    )
    write_json_atomic(_preflight_packet_path(proof_root), packet)
    return packet


def _collect_machine_error_code(
    *,
    unsafe: bool,
    preflight_ok: bool,
    ledger_fresh: bool,
    live_ok: bool,
    source_ok: bool,
    seal_ok: bool,
) -> str:
    if unsafe:
        return INTERACTIVE_UNSAFE_PACKET
    if not preflight_ok:
        return INTERACTIVE_PREFLIGHT_INVALID
    if not ledger_fresh:
        return INTERACTIVE_HOOK_LEDGER_NOT_FRESH
    if not live_ok:
        return INTERACTIVE_LIVE_PROVIDER_FAILED
    if not source_ok:
        return INTERACTIVE_HOOK_PROOF_FAILED
    if not seal_ok:
        return INTERACTIVE_SEAL_FAILED
    return INTERACTIVE_OK


def run_interactive_custom_codex_collect_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    preflight_packet_file: str,
    proof_dir: str | None = None,
    expected_text: str = DEFAULT_EXPECTED_TEXT,
    live_provider_proof_file: str | None = None,
) -> dict[str, Any]:
    proof_root = _proof_dir(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    prompt = str(prompt_text)
    expected = _safe_text(expected_text, limit=128)
    context_file = runtime_context_path(paths=paths, runtime_context_file=None)
    runtime_context, context_metadata = load_runtime_context_packet(context_file)
    secret_values = [prompt, expected] + _runtime_secret_values(runtime_context)

    preflight_path = Path(preflight_packet_file).expanduser()
    preflight_packet, preflight_metadata = _read_preflight_packet(preflight_path)
    ledger_path = hook_ledger_path(paths)
    ledger, ledger_metadata = _read_hook_ledger(ledger_path)
    prompt_digest = _sha256_text(prompt)
    context_digest = runtime_context_digest(runtime_context)

    preflight_failures: list[str] = []
    if preflight_metadata.get("preflight_packet_file_read") is not True:
        preflight_failures.append("preflight_packet_not_read")
    if preflight_packet.get("packet_kind") != INTERACTIVE_PREFLIGHT_PACKET_KIND:
        preflight_failures.append("preflight_packet_kind_invalid")
    if preflight_packet.get("status") != "ok":
        preflight_failures.append("preflight_packet_not_ok")
    if preflight_packet.get("prompt_digest") != prompt_digest:
        preflight_failures.append("preflight_prompt_digest_mismatch")
    if preflight_packet.get("runtime_context_digest") != context_digest:
        preflight_failures.append("preflight_runtime_context_digest_mismatch")
    if preflight_packet.get("ledger_cleared_before_prompt") is not True:
        preflight_failures.append("preflight_ledger_not_cleared")

    ledger_failures = _ledger_freshness_failures(
        ledger=ledger,
        ledger_metadata=ledger_metadata,
        preflight_packet=preflight_packet,
        prompt_digest=prompt_digest,
        context_digest=context_digest,
        ledger_path=ledger_path,
    )
    ledger_fresh = not ledger_failures

    preflight_ok = not preflight_failures
    if not preflight_ok or not ledger_fresh:
        suppress_reason = (
            "preflight_not_admitted" if not preflight_ok else "hook_ledger_not_fresh"
        )
        live_packet = _blocked_live_provider_packet(suppress_reason)
        _write_packet(_live_provider_packet_path(proof_root), live_packet)
        live_metadata = {
            "live_provider_proof_file_present": False,
            "live_provider_proof_file_read": False,
            "live_provider_proof_file_valid_json": False,
            "live_provider_proof_file_mapping": False,
            "live_provider_proof_file_path_recorded": False,
            "live_provider_suppressed_packet_written": True,
        }
        live_provider_source_kind = "suppressed_before_live_provider_call"
        external_models_dir_source = "not_selected_interactive_evidence_not_admitted"
    elif live_provider_proof_file:
        live_packet, live_metadata = _read_live_provider_packet(
            Path(live_provider_proof_file).expanduser()
        )
        _write_packet(_live_provider_packet_path(proof_root), live_packet)
        live_provider_source_kind = "file_backed_external_models_live_format_check"
        external_models_dir_source = "not_selected_file_backed_live_provider"
    else:
        live_packet, _route_id, external_models_dir_source = _run_live_provider_packet(
            paths=paths,
            runtime_context=runtime_context,
            prompt_text=prompt,
            expected_text=expected,
            proof_root=proof_root,
        )
        live_metadata = {
            "live_provider_proof_file_present": True,
            "live_provider_proof_file_read": True,
            "live_provider_proof_file_valid_json": isinstance(live_packet, Mapping),
            "live_provider_proof_file_mapping": isinstance(live_packet, Mapping),
            "live_provider_proof_file_path_recorded": False,
        }
        live_provider_source_kind = "collector_external_models_live_format_check"

    live_data = live_packet.get("data") if isinstance(live_packet.get("data"), Mapping) else {}
    live_ok = bool(
        live_packet.get("status") == "ok"
        and live_packet.get("machine_error_code") == "OK"
        and live_data.get("expected_text_observed") is True
        and live_data.get("fallback_used") is not True
    )

    changed_files = [
        str(_live_provider_packet_path(proof_root)),
        str(_source_packet_path(proof_root)),
        str(_source_seal_path(proof_root)),
        str(_source_seal_verify_path(proof_root)),
        str(_final_packet_path(proof_root)),
    ]
    source_packet = run_real_custom_codex_hook_proof_command(
        paths=paths,
        prompt_text=prompt,
        hook_ledger_file=str(ledger_path),
        runtime_context_file=str(context_file),
        live_provider_expected_text=expected,
        live_provider_proof_file=str(_live_provider_packet_path(proof_root)),
    )
    _write_packet(_source_packet_path(proof_root), source_packet)
    source_ok = source_packet.get("status") == "ok"

    hook_config_digest = _safe_text(
        source_packet.get("trusted_hook_config_sha256")
        or source_packet.get("loaded_hook_config_sha256"),
        limit=80,
    )
    source_seal_create, source_seal_verify, source_seal_changed = (
        _create_and_verify_source_seal(
            source_packet_path=_source_packet_path(proof_root),
            source_seal_path=_source_seal_path(proof_root),
            runtime_context_digest_value=context_digest,
            hook_ledger_digest=sha256_file(ledger_path),
            profile_hook_config_digest=hook_config_digest,
        )
    )
    changed_files.extend(source_seal_changed)
    _write_packet(_source_seal_verify_path(proof_root), source_seal_verify)
    seal_ok = source_seal_verify.get("status") == "ok"
    interactive_custom_codex_flow_proven = bool(
        preflight_ok
        and ledger_fresh
        and ledger.get("hook_producer_state") == "HOOK_RAN_CUSTOM_CODEX_PROVEN"
        and ledger.get("hook_trusted") is True
        and source_packet.get("user_prompt_submit_hook_ran") is True
    )
    approved_handoff_proven = bool(
        source_packet.get("approved_handoff_ready") is True
        and source_packet.get("handoff_delivered") is True
        and source_packet.get("delivery_observed") is True
    )
    ok = bool(
        interactive_custom_codex_flow_proven
        and live_ok
        and source_ok
        and approved_handoff_proven
        and seal_ok
    )
    blocking_reasons: list[str] = []
    blocking_reasons.extend(preflight_failures)
    blocking_reasons.extend(ledger_failures)
    if not live_ok:
        blocking_reasons.append("live_provider_not_proven")
    if not source_ok:
        blocking_reasons.append("user_prompt_submit_proof_not_ok")
    if not approved_handoff_proven:
        blocking_reasons.append("approved_handoff_not_proven")
    if not seal_ok:
        blocking_reasons.append("source_proof_seal_not_ok")

    unsafe = packets.command_packet_has_secret_leak(
        {
            "packet_kind": INTERACTIVE_COLLECT_PACKET_KIND,
            "source_packet_sha256": sha256_file(_source_packet_path(proof_root)),
            "source_seal_sha256": sha256_file(_source_seal_path(proof_root)),
        },
        secret_values=secret_values,
    )
    if unsafe:
        blocking_reasons.append("interactive_packet_secret_leak")

    machine_error_code = _collect_machine_error_code(
        unsafe=unsafe,
        preflight_ok=preflight_ok,
        ledger_fresh=ledger_fresh,
        live_ok=live_ok,
        source_ok=source_ok,
        seal_ok=seal_ok,
    )
    extra = {
        **context_metadata,
        **preflight_metadata,
        **ledger_metadata,
        **live_metadata,
        "schema_version": 1,
        "packet_kind": INTERACTIVE_COLLECT_PACKET_KIND,
        "runner_launch_surface": INTERACTIVE_COLLECT_SURFACE,
        "interactive_custom_codex_flow_proven": interactive_custom_codex_flow_proven,
        "user_prompt_submit_hook_ran": source_packet.get("user_prompt_submit_hook_ran")
        is True,
        "hook_ledger_fresh": ledger_fresh,
        "hook_ledger_freshness_failures": ledger_failures,
        "preflight_failures": preflight_failures,
        "hook_prompt_digest_bound": source_packet.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": source_packet.get(
            "hook_runtime_context_digest_bound"
        )
        is True,
        "runtime_context_bound": source_packet.get("hook_runtime_context_digest_bound")
        is True,
        "alias_context_read": source_packet.get("alias_context_read") is True,
        "allowed_api_route_ids_enforced": source_packet.get(
            "allowed_api_route_ids_enforced"
        )
        is True,
        "route_id_allowed": source_packet.get("route_id_allowed") is True,
        "api_lane_called": bool(live_ok and source_packet.get("api_lane_called") is True),
        "external_live_provider_response_proven": bool(
            live_ok and source_packet.get("external_live_provider_response_proven") is True
        ),
        "live_provider_response_proven": bool(
            live_ok and source_packet.get("live_provider_response_proven") is True
        ),
        "live_provider_packet_sha256": sha256_file(_live_provider_packet_path(proof_root)),
        "live_provider_source_kind": live_provider_source_kind,
        "external_models_dir_source": _safe_text(external_models_dir_source, limit=80),
        "external_models_dir_path_recorded": False,
        "approved_handoff_proven": approved_handoff_proven,
        "approved_handoff_ready": source_packet.get("approved_handoff_ready") is True,
        "handoff_delivered": source_packet.get("handoff_delivered") is True,
        "delivery_observed": source_packet.get("delivery_observed") is True,
        "codex_working_flow_delivery_proven": False,
        "does_not_prove_codex_working_flow_delivery": True,
        "strict_sealed_evidence": seal_ok,
        "proof_seal_verified": seal_ok,
        "source_proof_packet_kind": _safe_text(source_packet.get("packet_kind"), limit=80),
        "source_proof_machine_error_code": _safe_text(
            source_packet.get("machine_error_code"),
            limit=96,
        ),
        "source_proof_sha256": sha256_file(_source_packet_path(proof_root)),
        "source_seal_create_machine_error_code": _safe_text(
            source_seal_create.get("machine_error_code"),
            limit=96,
        ),
        "source_seal_machine_error_code": _safe_text(
            source_seal_verify.get("machine_error_code"),
            limit=96,
        ),
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "custom_codex_ui_visibility_proven": False,
        "native_free_chat_router_proven": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "browser_can_supply_hook_authority": False,
        "browser_can_supply_prompt_authority": False,
        "browser_can_supply_route_authority": False,
        "browser_can_supply_handoff_authority": False,
        "proof_dir_path_recorded": False,
        "preflight_packet_path_recorded": False,
        "hook_ledger_file_path_recorded": False,
        "live_provider_proof_file_path_recorded": False,
        "declared_write_surfaces": [
            "proof_dir",
            "proof_packets",
            "proof_seals",
        ],
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "proof_dir_written": True,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "changed_files": sorted(set(changed_files)),
    }
    packet = packets.build_command_packet(
        ok=ok and not unsafe,
        human_message=(
            "WBP proved interactive Custom Codex hook flow with live API lane and approved handoff."
            if ok and not unsafe
            else "WBP blocked interactive Custom Codex proof before product readiness."
        ),
        machine_error_code=machine_error_code,
        liveness="network_dependent" if not live_provider_proof_file else "not_applicable",
        severity="recoverable",
        operator_action="none" if ok and not unsafe else "stop",
        changed_files=sorted(set(changed_files)),
        effect=EFFECT_MUTATE,
        secret_values=secret_values,
        extra=extra,
    )
    write_json_atomic(_final_packet_path(proof_root), packet)
    return packet
