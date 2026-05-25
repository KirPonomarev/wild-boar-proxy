# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded non-native Codex CLI runner via WBP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .codex_account_selection import build_account_selection_packet
from .codex_custom_sessions import CodexCustomSessionManager
from .codex_model_registry import build_custom_model_registry_packet
from .operator_surface import OperatorSurfaceSession, stat_hash
from .runtime import RuntimePaths, build_command_payload


RUNNER_SURFACE = "wild-boar-proxy codex-runner smoke --json --prompt <text>"


def _targeted_current_codex_snapshot() -> dict[str, dict[str, Any]]:
    return {
        "codex_config": stat_hash(str(Path.home() / ".codex" / "config.toml")),
        "codex_auth": stat_hash(str(Path.home() / ".codex" / "auth.json")),
    }


def _compare_targeted_snapshots(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    comparisons: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        before_entry = before.get(key, {})
        after_entry = after.get(key, {})
        comparisons[key] = {
            "before": before_entry,
            "after": after_entry,
            "exists_unchanged": before_entry.get("exists") == after_entry.get("exists"),
            "size_unchanged": before_entry.get("size") == after_entry.get("size"),
            "mtime_ns_unchanged": before_entry.get("mtime_ns") == after_entry.get("mtime_ns"),
            "sha256_unchanged": before_entry.get("sha256") == after_entry.get("sha256"),
        }
    return comparisons


def _targeted_files_unchanged(comparisons: dict[str, dict[str, Any]]) -> bool:
    return all(
        entry.get("exists_unchanged") is True
        and entry.get("size_unchanged") is True
        and entry.get("mtime_ns_unchanged") is True
        and entry.get("sha256_unchanged") is True
        for entry in comparisons.values()
    )


def _normalize_wbp_command_result(result: dict[str, Any]) -> dict[str, Any]:
    packet = result.get("json") if isinstance(result, dict) else None
    if isinstance(packet, dict) and result.get("exit_code") == 0:
        return {
            "status": "ok",
            "machine_error_code": str(packet.get("machine_error_code") or "OK"),
            "human_message": str(packet.get("human_message") or "ok"),
            "packet": packet,
        }
    return {
        "status": "error",
        "machine_error_code": (
            str(packet.get("machine_error_code") or "COMMAND_UNAVAILABLE")
            if isinstance(packet, dict)
            else "COMMAND_UNAVAILABLE"
        ),
        "human_message": (
            str(packet.get("human_message") or "command unavailable")
            if isinstance(packet, dict)
            else "command unavailable"
        ),
        "packet": packet if isinstance(packet, dict) else {},
    }


def _selection_commands(operator: OperatorSurfaceSession) -> dict[str, dict[str, Any]]:
    return {
        "status": _normalize_wbp_command_result(operator.run_wbp(["status", "--json"])),
        "accounts_list": _normalize_wbp_command_result(
            operator.run_wbp(["accounts", "list", "--json"])
        ),
        "rollout_rotation_inspect": _normalize_wbp_command_result(
            operator.run_wbp(["rollout", "rotation", "inspect", "--json"])
        ),
        "external_models_routes_list": _normalize_wbp_command_result(
            operator.run_wbp(["external-models", "routes", "list", "--json"])
        ),
    }


def _api_snapshot_from_commands(commands: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    result = commands.get("external_models_routes_list")
    packet = result.get("packet") if isinstance(result, dict) else None
    data = packet.get("data") if isinstance(packet, dict) else None
    routes = data.get("routes") if isinstance(data, dict) else None
    if not isinstance(routes, list) or not routes:
        return None
    snapshot_routes: list[dict[str, Any]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "")
        if not route_id:
            continue
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        snapshot_routes.append(
            {
                "route_id": route_id,
                "provider": str(route.get("provider") or ""),
                "upstream_model": str(route.get("upstream_model") or ""),
                "enabled": route.get("enabled") is True,
                "secret_ref": str(auth.get("secret_ref") or ""),
            }
        )
    if not snapshot_routes:
        return None
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": snapshot_routes,
    }


def _selection_packet_for_external_route(
    model_id: str,
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else None
    route = None
    if isinstance(routes, list):
        for item in routes:
            if isinstance(item, dict) and str(item.get("route_id") or "") == model_id:
                route = item
                break
    if not isinstance(route, dict):
        return {
            "schema_version": 1,
            "status": "degraded",
            "machine_error_code": "EXTERNAL_API_ROUTE_NOT_VISIBLE",
            "selected_source_class": "none",
            "selected_backend_ref": "",
            "selected_backend_server_issued": False,
            "selected_route_ref": "",
            "selected_route_server_issued": False,
            "route_provenance_required": False,
            "route_provenance_proven": False,
            "source_provenance_status": "not_proven",
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selection_proven": False,
            "browser_selected_backend": False,
        }
    route_id = str(route.get("route_id") or "")
    secret_ref = str(route.get("secret_ref") or "")
    enabled = route.get("enabled") is True
    proven = enabled and bool(secret_ref)
    return {
        "schema_version": 1,
        "status": "ok" if proven else "degraded",
        "machine_error_code": "OK" if proven else "EXTERNAL_API_ROUTE_NOT_READY",
        "selected_source_class": "route_backed" if proven else "none",
        "selected_backend_ref": "",
        "selected_backend_server_issued": False,
        "selected_route_ref": route_id,
        "selected_route_server_issued": proven,
        "route_provenance_required": proven,
        "route_provenance_proven": proven,
        "source_provenance_status": "route_proven" if proven else "route_provenance_missing",
        "selection_dry_run_proven": proven,
        "live_selection_proven": False,
        "selection_proven": proven,
        "browser_selected_backend": False,
        "claim_gate_status": str(operator_status.get("claim_gate", {}).get("status") or ""),
    }


def _build_selection_packet(
    model_id: str,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if model_id.startswith("gpt-"):
        return build_account_selection_packet(commands, operator_status)
    return _selection_packet_for_external_route(model_id, operator_status, api_snapshot)


def _choose_server_model_id(
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> str:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    if isinstance(api_snapshot, dict):
        routes = api_snapshot.get("routes")
        if isinstance(routes, list):
            for route in routes:
                if isinstance(route, dict):
                    route_id = str(route.get("route_id") or "")
                    if route_id:
                        return route_id
    available = [
        str(entry.get("model_id") or "")
        for entry in registry.get("available_models", [])
        if isinstance(entry, dict) and str(entry.get("model_id") or "")
    ]
    reported = str(registry.get("reported_configured_model") or "")
    if reported and reported in available:
        return reported
    if available:
        return available[0]
    return ""


def run_codex_cli_runner_smoke(paths: RuntimePaths, prompt: str) -> dict[str, Any]:
    operator = OperatorSurfaceSession()
    manager = CodexCustomSessionManager()
    before = _targeted_current_codex_snapshot()
    operator_status = operator.status_payload()
    commands = _selection_commands(operator)
    api_snapshot = _api_snapshot_from_commands(commands)
    model_id = _choose_server_model_id(operator_status, api_snapshot)
    launch_packet: dict[str, Any]
    prompt_packet: dict[str, Any] = {}
    transcript_packet: dict[str, Any] = {}
    cleanup_packet: dict[str, Any] = {}
    raw_runner_result: dict[str, Any] = {}
    session_id = ""
    machine_error_code = "OK"
    human_message = "Codex CLI runner completed through WBP."

    if not model_id:
        registry = build_custom_model_registry_packet(
            operator_status,
            api_snapshot=api_snapshot,
        )
        return build_command_payload(
            ok=False,
            human_message="Codex CLI runner has no server-issued model to launch.",
            machine_error_code=str(
                registry.get("machine_error_code") or "SERVER_ISSUED_MODEL_REQUIRED"
            ),
            liveness="unknown",
            severity="recoverable",
            operator_action="repair_model_registry_truth",
            changed_files=[],
            extra={
                "consumer_kind": "codex_cli_runner",
                "native_app_claimed": False,
                "runner_launch_surface": RUNNER_SURFACE,
                "reusable_runner_launch_surface": True,
                "operator_status": operator_status,
                "model_registry_packet": registry,
                "api_snapshot_present": isinstance(api_snapshot, dict),
            },
        )

    selection = _build_selection_packet(model_id, commands, operator_status, api_snapshot)
    launch_packet = manager.create_packet(
        {"model_id": model_id},
        commands,
        operator_status,
        selection=selection,
        api_snapshot=api_snapshot,
    )
    if launch_packet.get("status") == "ok":
        session = launch_packet.get("session")
        if isinstance(session, dict):
            session_id = str(session.get("session_id") or "")

    try:
        if session_id:
            def runner(payload: dict[str, Any]) -> dict[str, Any]:
                nonlocal raw_runner_result
                raw_runner_result = operator.run_prompt(payload, trace_wbp=True)
                return raw_runner_result

            prompt_packet = manager.prompt_packet(
                session_id,
                {"prompt": prompt},
                runner,
                owner_authorized=True,
            )
            transcript_packet = manager.transcript_packet(session_id)
    finally:
        if session_id:
            cleanup_packet = manager.cleanup_packet(session_id)

    after = _targeted_current_codex_snapshot()
    comparisons = _compare_targeted_snapshots(before, after)
    targeted_unchanged = _targeted_files_unchanged(comparisons)
    cleanup_required = bool(session_id)
    if not cleanup_required:
        cleanup_packet = {
            "status": "ok",
            "machine_error_code": "NOT_APPLICABLE",
            "human_message": "Cleanup not required because no runner session was created.",
            "cleanup_performed": False,
            "owned_session_root_only": True,
            "cleanup_not_applicable": True,
        }
    cleanup_ok = cleanup_packet.get("status") == "ok"
    prompt_ok = prompt_packet.get("status") == "ok"
    process_network_observation = (
        prompt_packet.get("process_network_observation_packet")
        if isinstance(prompt_packet.get("process_network_observation_packet"), dict)
        else {}
    )
    direct_egress_classification = str(
        process_network_observation.get("classification") or "insufficient_observation"
    )
    direct_non_wbp_model_egress_absent_proven = (
        process_network_observation.get("direct_non_wbp_model_egress_absent_proven") is True
    )

    failed_checks: list[str] = []
    if launch_packet.get("status") != "ok":
        failed_checks.append("launch_packet_not_ok")
        machine_error_code = str(
            launch_packet.get("machine_error_code") or "CLI_RUNNER_LAUNCH_FAILED"
        )
        human_message = "Codex CLI runner launch packet did not admit execution."
    elif not prompt_ok:
        failed_checks.append("prompt_packet_not_ok")
        machine_error_code = str(
            prompt_packet.get("machine_error_code") or "CLI_RUNNER_PROMPT_FAILED"
        )
        human_message = "Codex CLI runner prompt did not complete with full proof."
    if cleanup_required and not cleanup_ok:
        failed_checks.append("cleanup_packet_not_ok")
        machine_error_code = str(
            cleanup_packet.get("machine_error_code") or "CLI_RUNNER_CLEANUP_FAILED"
        )
        human_message = "Codex CLI runner cleanup packet did not close cleanly."
    if not targeted_unchanged:
        failed_checks.append("current_codex_targeted_files_changed")
        machine_error_code = "CURRENT_CODEX_TARGETED_FILES_CHANGED"
        human_message = "Codex CLI runner touched targeted current Codex files."

    return build_command_payload(
        ok=not failed_checks,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness="healthy" if not failed_checks else "degraded",
        severity="recoverable",
        operator_action="none" if not failed_checks else "stop_and_diagnose",
        changed_files=[],
        extra={
            "consumer_kind": "codex_cli_runner",
            "native_app_claimed": False,
            "runner_launch_surface": RUNNER_SURFACE,
            "reusable_runner_launch_surface": True,
            "isolated_profile_location_repeatable": True,
            "session_root_scope": (
                launch_packet.get("session", {}).get("session_root_scope")
                if isinstance(launch_packet.get("session"), dict)
                else ""
            ),
            "selected_model_id": model_id,
            "selection_packet": selection,
            "api_snapshot_present": isinstance(api_snapshot, dict),
            "launch_packet": launch_packet,
            "prompt_packet": prompt_packet,
            "transcript_packet": transcript_packet,
            "cleanup_packet": cleanup_packet,
            "process_network_observation_packet": process_network_observation,
            "current_codex_observation": {
                "before": before,
                "after": after,
                "comparisons": comparisons,
                "targeted_files_unchanged": targeted_unchanged,
            },
            "raw_runner_warning_classes": (
                raw_runner_result.get("warning_classes")
                if isinstance(raw_runner_result.get("warning_classes"), list)
                else []
            ),
            "direct_egress_negative_status": direct_egress_classification,
            "direct_non_wbp_model_egress_absent_proven": direct_non_wbp_model_egress_absent_proven,
            "failed_checks": failed_checks,
        },
    )


__all__ = ["RUNNER_SURFACE", "run_codex_cli_runner_smoke"]
