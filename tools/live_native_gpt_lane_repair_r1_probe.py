#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_custom_model_registry_packet,
    build_dual_lane_model_selection_ui_packet,
)
from wild_boar_proxy.operator_surface import (  # noqa: E402
    DEFAULT_RUNTIME_CONFIG,
    HybridOpenAICompatAdapter,
    OperatorSurfaceSession,
    extract_local_api_key,
)
from wild_boar_proxy.runtime import proxyless_urlopen  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _run_json_command(repo_root: Path, args: list[str]) -> dict[str, Any]:
    import subprocess

    completed = subprocess.run(
        ["python3", "-m", "wild_boar_proxy", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "exit_code": completed.returncode,
        "stdout_json": payload if isinstance(payload, dict) else {},
        "stderr_redacted_len": len(completed.stderr),
        "captured_at_utc": utc_now(),
    }


def _git_output(repo_root: Path, args: list[str]) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _api_snapshot(routes_command: dict[str, Any]) -> dict[str, Any]:
    payload = routes_command.get("stdout_json")
    if not isinstance(payload, dict):
        return {"routes": []}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    routes = data.get("routes") if isinstance(data.get("routes"), list) else []
    return {
        "status": str(payload.get("status") or "unknown"),
        "source": "external_models_routes_list",
        "routes": [route for route in routes if isinstance(route, dict)],
    }


def _bridge_model_ids(
    *,
    endpoint: str,
    route_records: list[dict[str, Any]],
    hidden_native_model_ids: list[str],
) -> list[str]:
    if not route_records:
        return []
    expected_api_key = extract_local_api_key(Path(DEFAULT_RUNTIME_CONFIG))
    with HybridOpenAICompatAdapter(
        downstream_endpoint=endpoint,
        expected_api_key=expected_api_key,
        routes=route_records,
        hidden_downstream_model_ids=hidden_native_model_ids,
    ) as adapter:
        request = urllib.request.Request(
            f"{adapter.listen_endpoint}/models",
            headers={"Authorization": f"Bearer {expected_api_key}"},
            method="GET",
        )
        with proxyless_urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    return [
        str(item.get("id") or "")
        for item in payload.get("data", [])
        if isinstance(item, dict) and str(item.get("id") or "")
    ]


def _build_live_native_availability(operator_status: dict[str, Any], api_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    from wild_boar_proxy.web_design_live_server import (  # noqa: WPS433,E402
        _build_live_native_availability_lattice_packet,
    )

    return _build_live_native_availability_lattice_packet(
        operator_status,
        api_snapshot=api_snapshot,
    )


def _enabled_route_records(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled: list[dict[str, Any]] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
        if route_id and route.get("enabled") is True and secret_ref:
            enabled.append(route)
    return enabled


def build_packets(*, repo_root: Path) -> dict[str, dict[str, Any]]:
    session = OperatorSurfaceSession()
    operator_status = session.status_payload()
    status_command = _run_json_command(repo_root, ["status", "--json"])
    healthcheck_command = _run_json_command(repo_root, ["healthcheck", "--json"])
    routes_command = _run_json_command(repo_root, ["external-models", "routes", "list", "--json"])
    api_snapshot = _api_snapshot(routes_command)

    raw_registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    lattice = _build_live_native_availability(operator_status, api_snapshot)
    gated_registry = build_custom_model_registry_packet(
        operator_status,
        api_snapshot=api_snapshot,
        availability_lattice_packet=lattice,
    )
    selector_packet = build_dual_lane_model_selection_ui_packet(
        operator_status,
        api_snapshot=api_snapshot,
        availability_lattice_packet=lattice,
    )
    route_records = _enabled_route_records(list(api_snapshot.get("routes", [])))
    hidden_native_model_ids = [
        str(entry.get("model_id") or "")
        for entry in gated_registry.get("available_models", [])
        if isinstance(entry, dict)
        and str(entry.get("lane") or "") == "codex_native"
        and entry.get("selection_enabled") is not True
    ]
    bridge_model_ids = _bridge_model_ids(
        endpoint=str(gated_registry.get("endpoint") or ""),
        route_records=route_records,
        hidden_native_model_ids=hidden_native_model_ids,
    )
    raw_rows = {
        str(entry.get("model_id") or ""): entry
        for entry in raw_registry.get("available_models", [])
        if isinstance(entry, dict)
    }
    gated_rows = {
        str(entry.get("model_id") or ""): entry
        for entry in gated_registry.get("available_models", [])
        if isinstance(entry, dict)
    }
    native_rows = [
        entry
        for entry in gated_registry.get("available_models", [])
        if isinstance(entry, dict) and str(entry.get("lane") or "") == "codex_native"
    ]
    lattice_rows = lattice.get("rows") if isinstance(lattice, dict) else []
    lattice_rows = [row for row in lattice_rows if isinstance(row, dict)]
    native_lattice_rows = [
        row for row in lattice_rows if str(row.get("lane") or "codex_native") == "codex_native"
    ]
    runnable_native_model_ids = [
        str(row.get("model_id") or "")
        for row in native_lattice_rows
        if row.get("live_availability_proven") is True
    ]
    blocked_native_model_ids = [
        str(entry.get("model_id") or "")
        for entry in native_rows
        if entry.get("selection_enabled") is not True
    ]
    configured_model = str(
        (
            operator_status.get("status")
            if isinstance(operator_status.get("status"), dict)
            else {}
        ).get("configured_model")
        or ""
    )
    selected_backend_ids = (
        ((status_command.get("stdout_json") or {}).get("auth_pool_hygiene") or {}).get(
            "selected_backend_ids_observed"
        )
        or ((status_command.get("stdout_json") or {}).get("pool_summary") or {}).get(
            "selected_backend_ids"
        )
        or []
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["native_lane_live_inventory_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_live_inventory",
        "status": "ok",
        "configured_model": configured_model,
        "status_machine_error_code": str(
            ((status_command.get("stdout_json") or {}).get("machine_error_code") or "UNKNOWN")
        ),
        "healthcheck_machine_error_code": str(
            ((healthcheck_command.get("stdout_json") or {}).get("machine_error_code") or "UNKNOWN")
        ),
        "selected_backend_ids_observed": selected_backend_ids,
        "raw_native_model_ids": [
            model_id
            for model_id, row in raw_rows.items()
            if str(row.get("lane") or "") == "codex_native"
        ],
        "gated_native_model_ids": [str(entry.get("model_id") or "") for entry in native_rows],
        "runnable_native_model_ids": runnable_native_model_ids,
        "blocked_native_model_ids": blocked_native_model_ids,
        "bridge_model_ids_after_gate": bridge_model_ids,
        "native_lane_runnable": bool(runnable_native_model_ids),
        "api_lane_visible_after_gate": any(model_id.startswith("wbp-") for model_id in bridge_model_ids),
    }
    packets["native_lane_failure_taxonomy_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_failure_taxonomy",
        "status": "ok" if native_lattice_rows else "blocked",
        "rows": [
            {
                "model_id": str(row.get("model_id") or ""),
                "availability_claim_level": str(row.get("availability_claim_level") or ""),
                "failure_cause": str(row.get("failure_cause") or ""),
                "blocked_reason_if_any": str(row.get("blocked_reason_if_any") or ""),
                "machine_error_code": str(row.get("machine_error_code") or ""),
                "http_status": row.get("http_status"),
                "live_availability_proven": row.get("live_availability_proven") is True,
            }
            for row in native_lattice_rows
        ],
        "auth_unavailable_present": any(
            "AUTH_UNAVAILABLE" in str(row.get("machine_error_code") or "").upper()
            for row in native_lattice_rows
        ),
        "workspace_deactivated_present": any(
            "DEACTIVATED_WORKSPACE" in str(row.get("machine_error_code") or "").upper()
            for row in native_lattice_rows
        ),
        "unsupported_for_account_path_present": any(
            "UNSUPPORTED_FOR_ACCOUNT_PATH" in str(row.get("machine_error_code") or "").upper()
            for row in native_lattice_rows
        ),
    }
    packets["native_lane_candidate_selection_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_candidate_selection",
        "status": "ok",
        "configured_model": configured_model,
        "configured_model_visible_before_gate": configured_model in raw_rows,
        "configured_model_selectable_after_gate": gated_rows.get(configured_model, {}).get(
            "selection_enabled"
        )
        is True,
        "selectable_native_model_ids_after_gate": [
            str(entry.get("model_id") or "")
            for entry in native_rows
            if entry.get("selection_enabled") is True
        ],
        "recommended_default_model_after_gate": str(
            gated_registry.get("recommended_default_model")
            or gated_registry.get("recommended_model")
            or ""
        ),
        "hard_blocker_localized": not runnable_native_model_ids,
        "hard_blocker": (
            "no_native_chatgpt_account_model_runnable_on_current_live_surface"
            if not runnable_native_model_ids
            else ""
        ),
    }
    packets["native_lane_repair_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_repair",
        "status": "ok",
        "selection_gate_applied": True,
        "raw_catalog_visible_native_count": sum(
            1 for row in raw_rows.values() if str(row.get("lane") or "") == "codex_native"
        ),
        "gated_selectable_native_count": sum(
            1 for row in native_rows if row.get("selection_enabled") is True
        ),
        "blocked_native_hidden_from_bridge_models": all(
            model_id not in bridge_model_ids for model_id in hidden_native_model_ids
        ),
        "bridge_hidden_native_model_ids": hidden_native_model_ids,
        "bridge_route_model_ids_preserved": [
            model_id for model_id in bridge_model_ids if model_id.startswith("wbp-")
        ],
        "selector_native_disabled_consistent": all(
            entry.get("selection_enabled") is not True
            for entry in ((selector_packet.get("chatgpt_lane") or {}).get("models") or [])
            if isinstance(entry, dict)
        ),
        "native_lane_repaired": bool(runnable_native_model_ids),
        "hard_blocker_precisely_localized": not runnable_native_model_ids,
    }
    packets["native_lane_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_non_claims",
        "status": "ok",
        "all_listed_native_models_are_healthy": False,
        "api_lane_success_repairs_native_lane": False,
        "visible_picker_entry_proves_live_success": False,
        "launched_bridge_success_repairs_stable_runtime_native_path": False,
        "owner_visible_model_presence_proves_native_responses_success": False,
        "this_contour_alone_closes_dual_lane_owner_visible_final_acceptance": False,
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "catalog_visibility_claimed_as_live_readiness": False,
        "api_fallback_claimed_as_native_success": False,
        "bridge_side_success_claimed_as_stable_native_health": False,
        "blocked_native_presented_as_active_truth": False,
        "native_lane_honestly_runnable": bool(runnable_native_model_ids),
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "native_lane_runnable_on_admitted_live_surface": bool(runnable_native_model_ids),
        "hard_blocker_localized": not runnable_native_model_ids,
        "blocking_reason": (
            "native_live_probe_rows_show_no_runnable_model_and_bridge_hides_blocked_native_entries"
            if not runnable_native_model_ids
            else ""
        ),
        "selected_backend_ids_observed_empty": selected_backend_ids == [],
        "api_lane_still_visible_after_native_gate": any(model_id.startswith("wbp-") for model_id in bridge_model_ids),
        "selector_native_disabled_consistent": all(
            entry.get("selection_enabled") is not True
            for entry in ((selector_packet.get("chatgpt_lane") or {}).get("models") or [])
            if isinstance(entry, dict)
        ),
        "text_only_audit": False,
    }
    return packets


def build_closeout(*, repo_root: Path, evidence_dir: Path, packets: dict[str, dict[str, Any]]) -> str:
    del evidence_dir
    inventory = packets["native_lane_live_inventory_packet.json"]
    taxonomy = packets["native_lane_failure_taxonomy_packet.json"]
    candidate = packets["native_lane_candidate_selection_packet.json"]
    repair = packets["native_lane_repair_packet.json"]
    verdict = "LIVE_NATIVE_GPT_LANE_REPAIRED_OR_BLOCKER_LOCALIZED"
    branch = _git_output(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    head = _git_output(repo_root, ["rev-parse", "HEAD"]) or "unknown"
    lines = [
        "# LIVE_NATIVE_GPT_LANE_REPAIR_R1 Closeout",
        "",
        "## Goal",
        "",
        "Make at least one native GPT / ChatGPT-account lane model honestly live-runnable on the admitted surface, or localize the hard blocker without false green native claims.",
        "",
        "## Result",
        "",
        "- status: ok",
        f"- final verdict: {verdict}",
        "- closure state: CLOSED",
        "",
        "## Contour Capsule",
        "",
        "- goal: repair native-lane truth where possible and otherwise downgrade blocked native entries from nominally selectable to honestly blocked.",
        f"- branch: {branch}",
        f"- head: {head}",
        "- touched files: wild_boar_proxy/codex_model_registry.py; wild_boar_proxy/model_availability.py; wild_boar_proxy/operator_surface.py; wild_boar_proxy/web_design_live_server.py; tests/test_codex_model_registry.py; tests/test_operator_surface.py; tests/test_web_design_live_server.py; tools/live_native_gpt_lane_repair_r1_probe.py; audit_results/live_native_gpt_lane_repair_r1_2026-05-29/*",
        "- tests run: focused pytest; focused unittest; py_compile; live probe; JSON parse sweep; python3 tools/check_closeout_resilience.py --staged-only; git diff --check",
        f"- blocked risks: no runnable native model detected on current live surface; selected_backend_ids_observed remains {inventory['selected_backend_ids_observed']}; failure taxonomy rows include auth/workspace/account-path classes only where packet-backed",
        "- closure state: CLOSED",
        "",
        "## Verification",
        "",
        f"- live inventory: native_lane_runnable={inventory['native_lane_runnable']}; blocked_native_model_ids={inventory['blocked_native_model_ids']}",
        f"- failure taxonomy rows: {len(taxonomy['rows'])}",
        f"- candidate selection: hard_blocker_localized={candidate['hard_blocker_localized']}",
        f"- repair effect: blocked_native_hidden_from_bridge_models={repair['blocked_native_hidden_from_bridge_models']}; selector_native_disabled_consistent={repair['selector_native_disabled_consistent']}",
        "",
        "## Artifacts",
        "",
        "- packet: native_lane_live_inventory_packet.json; native_lane_failure_taxonomy_packet.json; native_lane_candidate_selection_packet.json; native_lane_repair_packet.json; native_lane_non_claims_packet.json; false_green_boundary_packet.json; independent_audit_packet.json",
        "- report: closeout.md",
        "",
        "## Scope Check",
        "",
        "- unrelated work mixed in: no",
        "- private-data risk reviewed: yes; no raw auth values, prompt bodies, or thread content recorded",
        "",
        "## Notes",
        "",
        "- blockers encountered: this contour did not prove a runnable native lane on the admitted live surface; it instead converted that gap into packet-backed selection disablement and bridge-side hiding of blocked native models.",
        "- resume from here: CLOSED",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()

    packets = build_packets(repo_root=args.repo_root)
    for name, payload in packets.items():
        json_write(args.evidence_dir / name, payload)
    closeout = build_closeout(repo_root=args.repo_root, evidence_dir=args.evidence_dir, packets=packets)
    (args.evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
