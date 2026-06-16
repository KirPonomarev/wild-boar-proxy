# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded non-native Codex CLI runner via WBP."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from .cli_runner_via_wbp import PRIMARY_MODEL_ID, build_codex_auth_command_config, remove_tree
from .codex_account_selection import build_account_selection_packet
from .codex_custom_sessions import CodexCustomSessionManager
from .codex_model_registry import (
    API_ROUTE_MODEL_LANE,
    CODEX_ACCOUNT_MODEL_LANE,
    build_custom_model_registry_packet,
    model_lane_classification_from_registry,
)
from .operator_surface import DEFAULT_ENDPOINT, OperatorSurfaceSession, WbpTraceObserver, clean_env, stat_hash
from .process_runner import (
    PROCESS_OK,
    PROCESS_TIMEOUT,
    BoundedProcessResult,
    run_bounded_process,
)
from .runtime import RuntimePaths, build_command_payload, build_launcher_subprocess_env


RUNNER_SURFACE = "wild-boar-proxy codex-runner smoke --json --prompt <text>"
REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _runner_warning_classes(stderr: str) -> list[str]:
    warnings: list[str] = []
    if "Failed to sync remote plugins" in stderr or "plugins/featured failed with status 401" in stderr:
        warnings.append("remote_plugin_sync_401")
    if "failed to refresh available models" in stderr:
        warnings.append("model_refresh_warning")
    return warnings


def _build_runner_env(paths: RuntimePaths, *, home: Path, codex_home: Path, auth_stamp: Path) -> dict[str, str]:
    env = clean_env()
    runtime_env = build_launcher_subprocess_env(paths)
    for key, value in runtime_env.items():
        if key.startswith("WBP_"):
            env[key] = value
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    env["WBP_TOKEN_COMMAND_AUDIT_STAMP_PATH"] = str(auth_stamp)
    env.pop("OPENAI_API_KEY", None)
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    return env


def _default_process_network_observation() -> dict[str, Any]:
    return {
        "status": "ok",
        "machine_error_code": "INSUFFICIENT_OBSERVATION",
        "classification": "insufficient_observation",
        "direct_non_wbp_model_egress_absent_proven": False,
        "process_tree_observed": False,
        "sample_count": 0,
        "observed_process_count_max": 0,
        "allowed_local_endpoints": [],
        "peer_endpoints": [],
        "non_local_peer_endpoints_present": False,
        "raw_pid_exposed": False,
        "pid_not_exposed_to_browser": True,
        "secret_value_recorded": False,
    }


def _run_wbp_cli_prompt(
    paths: RuntimePaths,
    *,
    codex_bin: Path,
    model_id: str,
    prompt: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    auth_command_path = REPO_ROOT / "wbp_codex_auth_command.py"
    tmp_root = Path(tempfile.mkdtemp(prefix="wbp-cli-runner-surface-"))
    home = tmp_root / "home"
    codex_home = tmp_root / "codex-home"
    workdir = tmp_root / "work"
    output_file = tmp_root / "last_message.txt"
    auth_stamp = tmp_root / "auth-command-stamp.txt"
    for path in (home, codex_home, workdir):
        path.mkdir(parents=True, exist_ok=True)

    env = _build_runner_env(paths, home=home, codex_home=codex_home, auth_stamp=auth_stamp)
    config_path = codex_home / "config.toml"
    config_text = ""
    process_result: BoundedProcessResult | None = None
    trace_packet: dict[str, Any] = {}
    started = time.time()
    with WbpTraceObserver(downstream_endpoint=DEFAULT_ENDPOINT) as trace:
        config_text = build_codex_auth_command_config(
            base_url=trace.listen_endpoint,
            auth_command_path=str(auth_command_path),
            model_id=model_id,
        )
        config_path.write_text(config_text, encoding="utf-8")
        process_result = run_bounded_process(
            [
                str(codex_bin),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "-C",
                str(workdir),
                "--json",
                "-o",
                str(output_file),
                "-",
            ],
            env=env,
            stdin_text=prompt,
            timeout_seconds=timeout_seconds,
        )
        trace_packet = trace.packet()
    if process_result.timed_out or process_result.machine_error_code == PROCESS_TIMEOUT:
        cleanup_packet = remove_tree(tmp_root)
        return {
            "status": "failed",
            "machine_error_code": "ENGINE_PROMPT_TIMEOUT",
            "human_message": "Codex CLI runner prompt timed out.",
            "final_message": "",
            "duration_seconds": round(time.time() - started, 3),
            "stdin_prompt_used": True,
            "temp_root_removed": cleanup_packet.get("status") == "passed",
            "secret_value_recorded": False,
            "configured_provider": "wbp",
            "configured_wire_api": "responses",
            "wbp_endpoint_configured": True,
            "config_endpoint_matches": True,
            "config_provider_matches": True,
            "config_wire_api_matches": True,
            "command_uses_stdin_dash": True,
            "command_json_mode": True,
            "env_codex_home_is_temp": True,
            "env_home_is_temp": True,
            "workdir_is_temp": True,
            "command_workdir_is_temp": True,
            "command_output_file_is_temp": True,
            "current_codex_home_used": False,
            "independent_wbp_trace_observed": False,
            "trace_observer_packet": trace_packet,
            "process_network_observation_packet": _default_process_network_observation(),
            "warning_classes": _runner_warning_classes(process_result.stderr),
            "auth_command_invoked": auth_stamp.exists(),
        }

    stdout = process_result.stdout if process_result is not None else ""
    stderr = process_result.stderr if process_result is not None else ""
    final_message = output_file.read_text(encoding="utf-8", errors="replace").strip() if output_file.exists() else ""
    auth_command_invoked = auth_stamp.exists()
    cleanup_packet = remove_tree(tmp_root)
    process_ok = process_result is not None and process_result.machine_error_code == PROCESS_OK
    return {
        "status": "ok" if process_ok and bool(final_message) else "failed",
        "machine_error_code": "OK" if process_ok and bool(final_message) else str(trace_packet.get("machine_error_code") or "ENGINE_PROMPT_FAILED"),
        "human_message": "Codex CLI runner prompt completed." if process_ok and bool(final_message) else "Codex CLI runner prompt failed.",
        "final_message": final_message,
        "duration_seconds": round(time.time() - started, 3),
        "stdin_prompt_used": True,
        "temp_root_removed": cleanup_packet.get("status") == "passed",
        "secret_value_recorded": False,
        "configured_provider": "wbp",
        "configured_wire_api": "responses",
        "wbp_endpoint_configured": True,
        "config_endpoint_matches": 'base_url = "' in config_text,
        "config_provider_matches": 'model_provider = "wbp"' in config_text,
        "config_wire_api_matches": 'wire_api = "responses"' in config_text,
        "command_uses_stdin_dash": True,
        "command_json_mode": True,
        "env_codex_home_is_temp": True,
        "env_home_is_temp": True,
        "workdir_is_temp": True,
        "command_workdir_is_temp": True,
        "command_output_file_is_temp": True,
        "current_codex_home_used": False,
        "independent_wbp_trace_observed": (
            trace_packet.get("request_observed") is True
            and trace_packet.get("response_observed") is True
            and trace_packet.get("forwarded_to_wbp") is True
            and trace_packet.get("path") == "/v1/responses"
            and isinstance(trace_packet.get("upstream_status"), int)
            and 200 <= int(trace_packet.get("upstream_status")) < 400
            and trace_packet.get("prompt_body_recorded") is False
            and trace_packet.get("auth_header_recorded") is False
            and trace_packet.get("secret_value_recorded") is False
        ),
        "trace_observer_packet": trace_packet,
        "process_network_observation_packet": _default_process_network_observation(),
        "warning_classes": _runner_warning_classes(stderr),
        "auth_command_invoked": auth_command_invoked,
        "stdout_sha256_present": bool(stdout),
    }


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


def _api_snapshot_has_server_routes(api_snapshot: dict[str, Any] | None) -> bool:
    routes = api_snapshot.get("routes") if isinstance(api_snapshot, dict) else None
    return any(
        isinstance(route, dict) and bool(str(route.get("route_id") or ""))
        for route in (routes if isinstance(routes, list) else [])
    )


def _cli_runner_model_gate_error(
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> str:
    if _api_snapshot_has_server_routes(api_snapshot):
        return ""
    models = operator_status.get("models") if isinstance(operator_status, dict) else None
    if not isinstance(models, dict):
        return "SERVER_ISSUED_MODEL_REQUIRED"
    raw_model_ids = models.get("model_ids")
    model_ids = [
        str(model_id)
        for model_id in (raw_model_ids if isinstance(raw_model_ids, list) else [])
        if str(model_id)
    ]
    if not model_ids:
        return (
            "NO_SERVER_MODELS_VISIBLE"
            if models.get("server_issued") is True
            else "SERVER_ISSUED_MODEL_REQUIRED"
        )
    if models.get("ok") is not True:
        return "CUSTOM_MODELS_NOT_VISIBLE"
    return ""


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
            "api_model_selected_by_user": True,
            "route_selected_by_user": False,
            "browser_selected_route": False,
            "route_candidate_source": "none",
            "route_candidate_classified": False,
            "route_static_readiness_classified": False,
            "route_execution_proven": False,
            "provider_response_proven": False,
            "secret_validity_proven": False,
            "live_compatibility_proven": False,
            "raw_route_exposed": False,
            "raw_secret_ref_exposed": False,
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selection_proven": False,
            "browser_selected_backend": False,
        }
    route_id = str(route.get("route_id") or "")
    secret_ref = str(route.get("secret_ref") or "")
    enabled = route.get("enabled") is True
    ready = enabled and bool(secret_ref)
    return {
        "schema_version": 1,
        "status": "ok" if ready else "degraded",
        "machine_error_code": "OK" if ready else "EXTERNAL_API_ROUTE_NOT_READY",
        "selected_source_class": "route_backed" if ready else "none",
        "selected_backend_ref": "",
        "selected_backend_server_issued": False,
        "selected_route_ref": route_id,
        "selected_route_server_issued": ready,
        "route_provenance_required": ready,
        "route_provenance_proven": False,
        "source_provenance_status": (
            "route_static_candidate_classified" if ready else "route_static_candidate_missing"
        ),
        "api_model_selected_by_user": True,
        "route_selected_by_user": False,
        "browser_selected_route": False,
        "route_candidate_source": "server_issued_route_registry" if route_id else "none",
        "route_candidate_classified": bool(route_id),
        "route_static_readiness_classified": ready,
        "route_execution_proven": False,
        "provider_response_proven": False,
        "secret_validity_proven": False,
        "live_compatibility_proven": False,
        "raw_route_exposed": False,
        "raw_secret_ref_exposed": False,
        "selection_dry_run_proven": ready,
        "live_selection_proven": False,
        "selection_proven": ready,
        "browser_selected_backend": False,
        "claim_gate_status": str(operator_status.get("claim_gate", {}).get("status") or ""),
    }


def _build_selection_packet(
    model_id: str,
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    lane_classification = model_lane_classification_from_registry(model_id, registry)
    model_lane = str(lane_classification.get("model_lane") or "")
    if model_lane == CODEX_ACCOUNT_MODEL_LANE:
        return build_account_selection_packet(commands, operator_status) | lane_classification
    if model_lane == API_ROUTE_MODEL_LANE:
        return _selection_packet_for_external_route(model_id, operator_status, api_snapshot) | lane_classification
    return {
        "schema_version": 1,
        "status": "rejected",
        "machine_error_code": "MODEL_LANE_NOT_CLASSIFIED",
        "selection_proven": False,
        "selected_source_class": "none",
        **lane_classification,
    }


def _choose_server_model_id(
    operator_status: dict[str, Any],
    api_snapshot: dict[str, Any] | None,
) -> str:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    available = [
        str(entry.get("model_id") or "")
        for entry in registry.get("available_models", [])
        if isinstance(entry, dict) and str(entry.get("model_id") or "")
    ]
    reported = str(registry.get("reported_configured_model") or "")
    native_available = [
        model_id
        for model_id in available
        if model_lane_classification_from_registry(model_id, registry).get("model_lane")
        == CODEX_ACCOUNT_MODEL_LANE
    ]
    if reported and reported in native_available:
        return reported
    if PRIMARY_MODEL_ID in available:
        return PRIMARY_MODEL_ID
    if native_available:
        return native_available[0]
    if reported and reported in available:
        return reported
    if isinstance(api_snapshot, dict):
        routes = api_snapshot.get("routes")
        if isinstance(routes, list):
            for route in routes:
                if isinstance(route, dict):
                    route_id = str(route.get("route_id") or "")
                    if route_id:
                        return route_id
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
    model_gate_error = _cli_runner_model_gate_error(operator_status, api_snapshot)
    model_id = "" if model_gate_error else _choose_server_model_id(operator_status, api_snapshot)
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
                model_gate_error
                or registry.get("machine_error_code")
                or "SERVER_ISSUED_MODEL_REQUIRED"
            ),
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "repair_model_registry_truth",
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
        {"primary_model_id": model_id},
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
                raw_runner_result = _run_wbp_cli_prompt(
                    paths,
                    codex_bin=operator.config.codex_bin,
                    model_id=str(payload.get("model_id") or model_id),
                    prompt=str(payload.get("prompt") or ""),
                )
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
    direct_non_wbp_model_egress_absent_proven = False

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
        operator_action="none" if not failed_checks else "stop",
        changed_files=[],
        extra={
            "next_action": "none" if not failed_checks else "stop_and_diagnose",
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
            "process_network_observation_counts_as_egress_proof": False,
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
            "direct_egress_negative_status": "not_claimed_in_cli_runner_contour",
            "process_network_observation_classification": direct_egress_classification,
            "direct_non_wbp_model_egress_absent_proven": direct_non_wbp_model_egress_absent_proven,
            "failed_checks": failed_checks,
        },
    )


__all__ = ["RUNNER_SURFACE", "run_codex_cli_runner_smoke"]
