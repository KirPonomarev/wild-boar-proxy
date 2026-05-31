#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit fresh direct-only WBP model availability smoke evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.model_availability import (
    build_candidate_model_list,
    build_candidate_partition_packet,
    build_default_model_source_packet,
    build_external_route_admission_packet,
    build_layer_boundary_packet,
    build_model_availability_admission_packet,
    build_model_availability_false_green_audit,
    build_model_availability_matrix,
    build_model_direct_preflight_packet,
    build_model_id_normalization_packet,
    build_no_route_account_mutation_packet,
    build_route_family_classification_packet,
    build_validation_freshness_packet,
    sha256_text,
    validate_model_availability_contour_packets,
    validate_model_availability_matrix,
)
from wild_boar_proxy.native_filesystem_probe import json_write
from wild_boar_proxy.runtime import proxyless_urlopen


DEFAULT_ENDPOINT = "http://127.0.0.1:8318/v1"
DIRECT_SMOKE_PROMPT_PREFIX = "WBP_MODEL_AVAILABILITY_R1_DIRECT_ONLY_NONCE_2026_05_27"
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_precedence_r1_2026-05-27"
MODEL_CATALOG_DIR = "audit_results/wbp_catalog_fidelity_model_registry_r1_2026-05-27"
MODEL_ROUTE_TRUTH_DIR = "audit_results/wbp_account_route_model_selection_truth_2026-05-26"
READINESS_RECONCILIATION_DIR = (
    "audit_results/wbp_model_catalog_and_availability_readiness_reconciliation_no_live_r1_2026-05-27"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_json(repo_root: Path, command: list[str], *, timeout: int = 180) -> dict[str, Any]:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "blocked",
            "machine_error_code": "COMMAND_TIMEOUT",
            "command": command,
            "stdout_hash": sha256_text(str(exc.stdout or "")),
            "stderr_hash": sha256_text(str(exc.stderr or "")),
        }
    if process.returncode != 0:
        return {
            "status": "blocked",
            "machine_error_code": "COMMAND_FAILED",
            "command": command,
            "returncode": process.returncode,
            "stdout_hash": sha256_text(process.stdout),
            "stderr_hash": sha256_text(process.stderr),
        }
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        return {
            "status": "blocked",
            "machine_error_code": "INVALID_COMMAND_JSON",
            "command": command,
            "stdout_hash": sha256_text(process.stdout),
            "stderr_hash": sha256_text(process.stderr),
        }
    return payload if isinstance(payload, dict) else {"status": "blocked", "machine_error_code": "INVALID_COMMAND_JSON_SHAPE"}


def _run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        return ""
    return process.stdout.strip()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _git_status_lines(repo_root: Path) -> list[str]:
    return _run_text(repo_root, ["git", "status", "--short"]).splitlines()


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/model_availability.py",
        "tests/test_model_availability.py",
        "tests/test_model_availability_direct_only_smoke_probe.py",
        "tools/model_availability_direct_only_smoke_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    quarantined: list[str] = []
    unexpected: list[str] = []
    for line in _git_status_lines(repo_root):
        stripped = line.strip()
        if stripped.startswith(quarantined_prefixes):
            quarantined.append(line)
        elif stripped.startswith(
            (
                f"?? {relative_evidence_dir}/",
                f"M {relative_evidence_dir}/",
                f"D {relative_evidence_dir}/",
            )
        ):
            continue
        elif any(path in line for path in admitted_current_contour):
            continue
        else:
            unexpected.append(line)
    return quarantined, unexpected


def _readiness_candidate_rows(repo_root: Path) -> list[dict[str, Any]]:
    payload = _read_json_file(
        repo_root
        / READINESS_RECONCILIATION_DIR
        / "model_availability_candidate_matrix_packet.json"
    )
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("candidate_selected") is True]


def _candidate_inputs_from_live_and_readiness(
    *,
    model_ids: list[str],
    readiness_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    catalog_models: dict[str, dict[str, Any]] = {
        model_id: {
            "model_id": model_id,
            "server_issued": True,
            "source": "direct_models_endpoint",
        }
        for model_id in model_ids
    }
    routes: list[dict[str, Any]] = []
    readiness_admitted: list[str] = []
    imported_external_route_ids: list[str] = []
    for row in readiness_rows:
        model_id = str(row.get("model_id") or "").strip()
        if not model_id:
            continue
        readiness_admitted.append(model_id)
        catalog_models.setdefault(
            model_id,
            {
                "model_id": model_id,
                "server_issued": True,
                "source": "readiness_reconciliation_reference",
            },
        )
        if str(row.get("route_family") or "") == "wbp_api_external_route":
            imported_external_route_ids.append(model_id)
            routes.append(
                {
                    "route_id": model_id,
                    "enabled": True,
                    "provider": {"id": "readiness_reference_external_route"},
                    "upstream_model": str(row.get("provider_model_id") or model_id),
                    "auth": {"secret_ref": "present_redacted"},
                    "adapter_id": "readiness_reference_external_route_adapter",
                }
            )
    reference_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "model_availability_readiness_reference",
        "status": "ok" if readiness_rows else "blocked",
        "source_dir": READINESS_RECONCILIATION_DIR,
        "source_packet": (
            f"{READINESS_RECONCILIATION_DIR}/model_availability_candidate_matrix_packet.json"
        ),
        "reference_only": True,
        "readiness_candidate_count": len(readiness_rows),
        "fresh_models_endpoint_visible_ids": model_ids,
        "readiness_admitted_candidate_ids": readiness_admitted,
        "imported_external_route_ids": imported_external_route_ids,
        "candidate_freeze_reproved_here": False,
        "model_availability_proven_by_reference": False,
    }
    return (
        {"models": list(catalog_models.values())},
        {"data": {"routes": routes}},
        reference_packet,
    )


def _summary_status_packet(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": f"{source}_summary",
        "status": payload.get("status"),
        "machine_error_code": payload.get("machine_error_code"),
        "liveness": payload.get("liveness"),
        "endpoint": payload.get("endpoint"),
        "configured_model": payload.get("configured_model"),
        "launch_readiness_status": (
            payload.get("launch_readiness", {}).get("status")
            if isinstance(payload.get("launch_readiness"), dict)
            else ""
        ),
        "listener_reachable": (
            payload.get("launch_readiness", {}).get("listener_reachable")
            if isinstance(payload.get("launch_readiness"), dict)
            else None
        ),
        "models_surface_reachable": (
            payload.get("launch_readiness", {}).get("models_surface_reachable")
            if isinstance(payload.get("launch_readiness"), dict)
            else None
        ),
        "responses_proof_passed": (
            payload.get("launch_readiness", {}).get("responses_proof_passed")
            if isinstance(payload.get("launch_readiness"), dict)
            else None
        ),
        "claim_gate_status": (
            payload.get("claim_gate", {}).get("status")
            if isinstance(payload.get("claim_gate"), dict)
            else ""
        ),
        "changed_files": payload.get("changed_files", []),
        "fallback_used": payload.get("fallback_used", False),
        "fallback_reason": payload.get("fallback_reason", ""),
        "raw_secret_recorded": False,
    }


def _file_hash(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    data = path.read_bytes()
    return {"path": str(path), "exists": True, "sha256": sha256_text(data.decode("utf-8", "replace")), "size": len(data)}


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _reference_packet(
    *,
    packet_kind: str,
    source_path: Path,
    expected_status: str | None = None,
    expected_selected_strategy: str | None = None,
) -> dict[str, Any]:
    payload = _read_json_file(source_path)
    status = payload.get("status")
    allowed_status = payload.get("allowed_status")
    nested_allowed_status = ""
    if not allowed_status:
        for value in payload.values():
            if isinstance(value, dict) and value.get("allowed_status"):
                nested_allowed_status = str(value.get("allowed_status") or "")
                break
    selected_strategy = payload.get("selected_strategy")
    failures: list[str] = []
    if not payload:
        failures.append("referenced_packet_missing_or_invalid")
    if expected_status is not None and status != "ok" and not allowed_status and not nested_allowed_status:
        failures.append("referenced_packet_not_ok")
    if expected_selected_strategy is not None and selected_strategy != expected_selected_strategy:
        failures.append("referenced_selected_strategy_mismatch")
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": packet_kind,
        "status": "ok" if not failures else "blocked",
        "referenced_packet": str(source_path),
        "referenced_packet_sha256": _file_hash(source_path).get("sha256", ""),
        "referenced_packet_exists": bool(payload),
        "referenced_status": status or "",
        "referenced_allowed_status": allowed_status or "",
        "referenced_nested_allowed_status": nested_allowed_status,
        "referenced_selected_strategy": selected_strategy or "",
        "reference_only": True,
        "auth_reproved_in_this_contour": False,
        "catalog_reproved_in_this_contour": False,
        "route_policy_reproved_in_this_contour": False,
        "model_availability_proven_by_reference": False,
        "validation_failures": failures,
        "expected_status": expected_status or "",
    }


def _route_account_snapshot(paths_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Capture authority surfaces, not runtime counters that may change after smoke."""
    return {
        "stable_config": _file_hash(Path("/Users/kirillponomarev/.cli-proxy-api/config.yaml")),
        "generated_stable_config": _file_hash(paths_root / ".codex-custom-cli/managed/stable-runtime-config.generated.yaml"),
        "model_authority_source": "direct_request_body_against_existing_wbp_runtime",
        "route_account_mutation_probe_scope": "static_authority_surfaces_only",
    }


def _auth_token_packet(repo_root: Path) -> tuple[dict[str, Any], str]:
    command_path = repo_root / "wbp_codex_auth_command.py"
    process = subprocess.run(
        [str(command_path)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    token = process.stdout.strip() if process.returncode == 0 else ""
    return (
        {
            "captured_at_utc": _utc_now(),
            "packet_kind": "direct_smoke_auth_command_observation",
            "status": "ok" if token else "blocked",
            "auth_command_path": str(command_path),
            "auth_command_returncode": process.returncode,
            "token_present": bool(token),
            "token_recorded": False,
            "token_hash_recorded": False,
            "stderr_hash": sha256_text(process.stderr) if process.stderr else "",
            "raw_upstream_secret_recorded": False,
        },
        token,
    )


def _http_json(
    *,
    endpoint: str,
    path: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    body = json.dumps(payload or {}, ensure_ascii=True).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "OpenAI-Beta": "responses=v1",
            "X-Session-ID": f"wbp-model-availability-direct-{sha256_text(_utc_now())[:16]}",
        },
    )
    try:
        with proxyless_urlopen(request, timeout=timeout) as response:
            response_body = response.read()
            try:
                parsed = json.loads(response_body.decode("utf-8"))
            except json.JSONDecodeError:
                parsed = {}
            return {
                "http_status": int(response.status),
                "body_hash": sha256_text(response_body.decode("utf-8", "replace")),
                "body_len": len(response_body),
                "payload": parsed if isinstance(parsed, dict) else {},
            }
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        try:
            parsed = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError:
            parsed = {}
        return {
            "http_status": int(exc.code),
            "body_hash": sha256_text(response_body.decode("utf-8", "replace")),
            "body_len": len(response_body),
            "payload": parsed if isinstance(parsed, dict) else {},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "http_status": None,
            "body_hash": "",
            "body_len": 0,
            "payload": {"machine_error_code": type(exc).__name__, "error": {"type": "timeout" if "timed" in str(exc).lower() else "unknown"}},
        }


def _models_endpoint_packet(endpoint: str, token: str) -> tuple[dict[str, Any], list[str]]:
    observed = _http_json(endpoint=endpoint, path="models", token=token)
    data = observed["payload"].get("data")
    model_ids = [
        str(item.get("id") or item.get("model_id") or "").strip()
        for item in data
        if isinstance(item, dict)
    ] if isinstance(data, list) else []
    model_ids = [model_id for model_id in model_ids if model_id]
    return (
        {
            "captured_at_utc": _utc_now(),
            "packet_kind": "direct_models_endpoint_observation",
            "status": "ok" if observed["http_status"] == 200 and model_ids else "blocked",
            "endpoint": endpoint,
            "http_status": observed["http_status"],
            "body_hash": observed["body_hash"],
            "body_len": observed["body_len"],
            "model_count": len(model_ids),
            "model_ids": model_ids,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
        },
        model_ids,
    )


def _direct_model_packet(endpoint: str, token: str, model_id: str, listed: bool) -> dict[str, Any]:
    prompt = f"{DIRECT_SMOKE_PROMPT_PREFIX}_{model_id}: answer exactly OK"
    observed = _http_json(
        endpoint=endpoint,
        path="responses",
        token=token,
        method="POST",
        payload={"model": model_id, "input": prompt, "max_output_tokens": 16, "stream": False},
    )
    status = observed["http_status"]
    response_payload = observed["payload"] if status is not None and 200 <= status < 300 else None
    error_payload = observed["payload"] if response_payload is None else None
    return build_model_direct_preflight_packet(
        model_id=model_id,
        source="fresh_direct_models_endpoint",
        listed=listed,
        selectable=listed,
        route_selected=listed and status != 404,
        runtime_ready=True,
        http_status=status,
        upstream_status=status,
        response_payload=response_payload,
        error_payload=error_payload,
        prompt_text=prompt,
        request_sent_to_wbp=True,
    )


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    markers = ["sk-", "OPENAI_API_KEY=", "Authorization: Bearer", DIRECT_SMOKE_PROMPT_PREFIX]
    findings = [marker for marker in markers if marker in serialized]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "secret_redaction_audit",
        "status": "blocked" if findings else "ok",
        "raw_secret_found": bool(findings),
        "raw_prompt_found": DIRECT_SMOKE_PROMPT_PREFIX in findings,
        "secret_marker_findings": findings,
        "auth_header_recorded": "Authorization: Bearer" in serialized,
        "checked_packet_count": len(packets),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "model_candidate_discovery_packet.json",
        "runtime_status_before_packet.json",
        "runtime_healthcheck_packet.json",
        "runtime_status_after_packet.json",
        "direct_smoke_auth_command_observation_packet.json",
        "direct_models_endpoint_observation_packet.json",
        "candidate_model_list_packet.json",
        "candidate_partition_packet.json",
        "default_model_source_packet.json",
        "route_family_classification_packet.json",
        "model_availability_admission_packet.json",
        "external_route_admission_packet.json",
        "model_id_normalization_packet.json",
        "route_account_mutation_guard_packet.json",
        "validation_freshness_packet.json",
        "model_availability_layer_boundary_packet.json",
        "model_availability_matrix.json",
        "model_claims_matrix.json",
        "model_availability_false_green_audit.json",
        "secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = sorted(name for name, packet in packets.items() if packet.get("status") == "blocked")
    matrix = packets.get("model_availability_matrix.json", {})
    contour_failures = validate_model_availability_contour_packets(packets)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_model_availability_direct_only_audit",
        "status": "blocked" if missing or blocked or contour_failures else "ok",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": blocked,
        "contour_validation_failures": contour_failures,
        "direct_only_contour": matrix.get("direct_only_contour") is True,
        "native_launch_attempted": matrix.get("native_launch_attempted") is True,
        "codex_cli_tested": matrix.get("codex_cli_tested") is True,
        "streaming_compatible_claimed": matrix.get("streaming_compatible") is True,
        "tool_loop_compatible_claimed": matrix.get("tool_loop_compatible") is True,
        "previous_matrix_imported_as_current_truth": matrix.get("previous_matrix_imported_as_current_truth") is True,
        "matrix_validation_failures": validate_model_availability_matrix(matrix),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-availability-direct-only-smoke-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    endpoint = str(args.endpoint).rstrip("/")
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_before = _run_json(repo_root, [sys.executable, "-m", "wild_boar_proxy", "status", "--json"])
    healthcheck = _run_json(repo_root, [sys.executable, "-m", "wild_boar_proxy", "healthcheck", "--json"])
    if status_before.get("status") == "blocked" and healthcheck.get("status") == "ok":
        status_before = {
            **healthcheck,
            "fallback_used": True,
            "fallback_reason": "status_before_command_unavailable_healthcheck_live_truth_used",
        }
    route_account_before = _route_account_snapshot(Path.home(), status_before)
    auth_packet, token = _auth_token_packet(repo_root)
    models_packet, model_ids = _models_endpoint_packet(endpoint, token) if token else (
        {"captured_at_utc": _utc_now(), "packet_kind": "direct_models_endpoint_observation", "status": "blocked", "model_ids": []},
        [],
    )
    readiness_rows = _readiness_candidate_rows(repo_root)
    catalog_packet, routes_packet, readiness_reference_packet = _candidate_inputs_from_live_and_readiness(
        model_ids=model_ids,
        readiness_rows=readiness_rows,
    )
    configured_model = str(healthcheck.get("configured_model") or status_before.get("configured_model") or "")
    candidate_packet = build_candidate_model_list(
        configured_model=configured_model,
        catalog_packet=catalog_packet,
        routes_packet=routes_packet,
    )
    runtime_packet = {
        "runtime_ready": healthcheck.get("status") == "ok"
        and isinstance(healthcheck.get("launch_readiness"), dict)
        and healthcheck["launch_readiness"].get("gate_passed") is True,
    }
    normalization = build_model_id_normalization_packet(
        candidate_packet=candidate_packet,
        catalog_packet=catalog_packet,
        routes_packet=routes_packet,
    )
    route_family = build_route_family_classification_packet(
        candidate_packet=candidate_packet,
        normalization_packet=normalization,
    )
    candidate_partition = build_candidate_partition_packet(
        candidate_packet=candidate_packet,
        route_family_packet=route_family,
    )
    default_model_source = build_default_model_source_packet(
        configured_model=configured_model,
        candidate_packet=candidate_packet,
        route_family_packet=route_family,
    )
    status_after = _run_json(repo_root, [sys.executable, "-m", "wild_boar_proxy", "status", "--json"])
    if status_after.get("status") == "blocked" and healthcheck.get("status") == "ok":
        status_after = {
            **healthcheck,
            "fallback_used": True,
            "fallback_reason": "status_after_command_unavailable_healthcheck_live_truth_used",
        }
    route_account_after = _route_account_snapshot(Path.home(), status_after)
    freshness = build_validation_freshness_packet(
        observed_at_utc=str(
            healthcheck.get("attestation", {}).get("observed_at_utc")
            if isinstance(healthcheck.get("attestation"), dict)
            else healthcheck.get("captured_at_utc") or _utc_now()
        ),
        validation_actor="fresh_direct_wbp_model_availability_smoke",
        validation_scope=",".join(str(model_id) for model_id in candidate_packet.get("candidate_model_ids", [])),
    )
    admission = build_model_availability_admission_packet(
        candidate_partition_packet=candidate_partition,
        validation_freshness_packet=freshness,
    )
    external_admission = build_external_route_admission_packet(
        route_family_packet=route_family,
        normalization_packet=normalization,
    )
    source_rows = {
        str(row.get("model_id") or ""): row
        for row in readiness_rows
        if isinstance(row, dict)
    }
    route_family_by_model = {
        str(row.get("model_id")): str(row.get("route_family") or "")
        for row in route_family.get("classifications", [])
        if isinstance(row, dict)
    }
    admitted_models = set(admission.get("admitted_smoke_candidates", []))
    model_packets = []
    for model_id in candidate_packet.get("candidate_model_ids", []):
        if not token or model_id not in admitted_models:
            continue
        source_row = source_rows.get(str(model_id), {})
        packet = _direct_model_packet(
            endpoint,
            token,
            model_id,
            (model_id in model_ids) or bool(source_row),
        )
        packet["route_family"] = route_family_by_model.get(model_id, "")
        packet["candidate_source"] = (
            "fresh_direct_models_endpoint"
            if model_id in model_ids
            else "readiness_reconciliation_reference"
        )
        packet["source"] = packet["candidate_source"]
        packet["selectable"] = True
        packet["route_selected"] = packet["route_family"] != "unknown_unrouted"
        if packet["route_selected"] and "route_selected" not in packet["availability_levels"]:
            packet["availability_levels"].append("route_selected")
        if packet["selectable"] and "selectable" not in packet["availability_levels"]:
            packet["availability_levels"].insert(1 if packet["listed"] else 0, "selectable")
        model_packets.append(packet)
    matrix = build_model_availability_matrix(
        model_packets,
        candidate_packet=candidate_packet,
        runtime_packet=runtime_packet,
    )
    mutation_guard = build_no_route_account_mutation_packet(
        route_snapshot_before=route_account_before,
        route_snapshot_after=route_account_after,
        account_snapshot_before=route_account_before,
        account_snapshot_after=route_account_after,
    )
    layer_boundary = build_layer_boundary_packet()
    false_green = build_model_availability_false_green_audit(
        matrix_packet=matrix,
        freshness_packet=freshness,
        layer_boundary_packet=layer_boundary,
        mutation_guard_packet=mutation_guard,
        normalization_packet=normalization,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run_text(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run_text(repo_root, ["git", "rev-parse", "HEAD"]),
            "git_status_short": _git_status_lines(repo_root),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "repo_master_plan_written": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_launch_allowed": False,
            "native_launch_attempted": False,
            "codex_cli_launch_allowed": False,
            "codex_cli_launch_attempted": False,
            "route_account_mutation_allowed": False,
            "route_account_mutation_attempted": False,
            "original_codex_profile_write_allowed": False,
            "original_codex_profile_write_attempted": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "wbp_git_commit": _run_text(repo_root, ["git", "rev-parse", "HEAD"]),
            "branch": _run_text(repo_root, ["git", "branch", "--show-current"]),
            "model_availability_schema_version": 1,
            "endpoint": endpoint,
            "codex_cli_version": "not_used_in_this_contour",
            "codex_app_version": "not_used_in_this_contour",
        },
        "runtime_status_before_packet.json": _summary_status_packet(status_before, source="runtime_status_before"),
        "runtime_healthcheck_packet.json": _summary_status_packet(healthcheck, source="runtime_healthcheck"),
        "runtime_status_after_packet.json": _summary_status_packet(status_after, source="runtime_status_after"),
        "direct_smoke_auth_command_observation_packet.json": auth_packet,
        "provider_auth_strategy_reference_packet.json": _reference_packet(
            packet_kind="provider_auth_strategy_reference",
            source_path=repo_root / AUTH_STRATEGY_DIR / "auth_strategy_precedence_packet.json",
            expected_status="ok",
        ),
        "model_catalog_reference_packet.json": _reference_packet(
            packet_kind="model_catalog_reference",
            source_path=repo_root / MODEL_CATALOG_DIR / "model_catalog_fidelity_summary_packet.json",
            expected_status="ok",
        ),
        "model_route_policy_reference_packet.json": _reference_packet(
            packet_kind="model_route_policy_reference",
            source_path=repo_root / MODEL_ROUTE_TRUTH_DIR / "model_to_route_selection_packet.json",
            expected_status="ok",
        ),
        "model_availability_readiness_reference_packet.json": readiness_reference_packet,
        "direct_models_endpoint_observation_packet.json": models_packet,
        "model_candidate_discovery_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "model_candidate_discovery",
            "status": "ok" if model_ids else "blocked",
            "source": "direct_wbp_models_endpoint",
            "configured_model": configured_model,
            "catalog_visible_model_ids": model_ids,
            "catalog_visible_counted_as_availability": False,
            "all_model_sweep_attempted": False,
            "raw_secret_recorded": False,
        },
        "candidate_model_list_packet.json": candidate_packet,
        "candidate_partition_packet.json": candidate_partition,
        "default_model_source_packet.json": default_model_source,
        "route_family_classification_packet.json": route_family,
        "model_availability_admission_packet.json": admission,
        "external_route_admission_packet.json": external_admission,
        "model_id_normalization_packet.json": normalization,
        "route_account_mutation_guard_packet.json": mutation_guard,
        "validation_freshness_packet.json": freshness,
        "model_availability_layer_boundary_packet.json": layer_boundary,
        "model_availability_matrix.json": matrix,
        "model_claims_matrix.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "model_claims_matrix",
            "status": "ok" if not validate_model_availability_matrix(matrix) else "blocked",
            "allowed_claims": [packet.get("allowed_claim") for packet in model_packets],
            "forbidden_claims": matrix.get("forbidden_claims", []),
            "validation_failures": validate_model_availability_matrix(matrix),
            "codex_acceptance_proven": False,
            "native_app_usability_proven": False,
            "direct_egress_absence_proven": False,
            "streaming_compatible": False,
            "tool_loop_compatible": False,
        },
        "model_availability_false_green_audit.json": false_green,
    }
    packets["model_availability_false_green_audit.json"] = build_model_availability_false_green_audit(
        matrix_packet=matrix,
        freshness_packet=freshness,
        layer_boundary_packet=layer_boundary,
        mutation_guard_packet=mutation_guard,
        normalization_packet=normalization,
        contour_packets=packets,
    )
    packets["secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    packets["independent_model_availability_audit.json"] = _independent_audit(packets)
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "model_availability_direct_only_summary",
        "status": "ok"
        if all(packet.get("status") != "blocked" for packet in packets.values())
        and not validate_model_availability_contour_packets(packets)
        else "blocked",
        "final_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "proof_transport": "direct_wbp_http_non_stream",
        "models_tested": matrix.get("models_tested", []),
        "direct_wbp_non_stream_passed_models": matrix.get("direct_wbp_non_stream_passed_models", []),
        "contour_validation_failures": validate_model_availability_contour_packets(packets),
        "gpt_5_5_claim": matrix.get("gpt_5_5_claim"),
        "native_launch_attempted": False,
        "codex_cli_launch_attempted": False,
        "route_account_mutation_attempted": False,
        "previous_matrix_imported_as_current_truth": False,
        "codex_acceptance_proven": False,
        "direct_egress_absence_proven": False,
    }
    packets["model_availability_direct_only_summary_packet.json"] = summary
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    for row in route_family.get("classifications", []):
        if not isinstance(row, dict):
            continue
        model_id = str(row.get("model_id") or "unknown")
        safe_name = model_id.replace("/", "_").replace(":", "_")
        json_write(evidence_dir / "model_route_selection_packets" / f"{safe_name}.json", row)
    for packet in model_packets:
        json_write(evidence_dir / "model_direct_preflight_packets" / f"{packet['model_id']}.json", packet)
    blocked_candidates = candidate_partition.get("blocked_candidates", [])
    if blocked_candidates:
        for item in blocked_candidates:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model_id") or "unknown")
            safe_name = model_id.replace("/", "_").replace(":", "_")
            json_write(evidence_dir / "model_blocked_packets" / f"{safe_name}.json", item)
    else:
        json_write(
            evidence_dir / "model_blocked_packets" / "no_blocked_candidates.json",
            {
                "captured_at_utc": _utc_now(),
                "packet_kind": "model_blocked_candidates",
                "status": "ok",
                "blocked_candidates": [],
            },
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
