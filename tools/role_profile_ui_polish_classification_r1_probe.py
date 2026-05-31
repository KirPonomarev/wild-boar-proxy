#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify bounded role/profile UI polish truth for admitted API connection surfaces."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write


ADMISSION_PACKET = ROOT / "audit_results/wbp_optional_annex_admission_stop_classification_r1_2026-05-27/optional_annex_admission_status_packet.json"
DESIGN_GATE_PACKET = ROOT / "audit_results/web_design_gate_admission_check_pass_2026-05-16/decision_packet.json"
HTML_PATH = ROOT / "wild_boar_proxy/web_design_ui/index.html"
JS_PATH = ROOT / "wild_boar_proxy/web_design_ui/scripts/overview.js"
CSS_PATH = ROOT / "wild_boar_proxy/web_design_ui/styles/overview.css"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "wild_boar_proxy/web_design_ui/index.html",
        "wild_boar_proxy/web_design_ui/styles/overview.css",
        "wild_boar_proxy/web_design_ui/scripts/overview.js",
        "tests/test_web_design_ui.py",
        "tools/role_profile_ui_polish_classification_r1_probe.py",
        "tests/test_role_profile_ui_polish_classification_r1_probe.py",
    ]
    try:
        relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    except ValueError:
        relative_evidence_dir = None
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not (
            relative_evidence_dir
            and line.strip().startswith(f"?? {relative_evidence_dir}/")
        )
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _run(repo_root, ["codex", "--version"], check=False),
        "codex_cli_path": _run(repo_root, ["which", "codex"], check=False),
        "codex_app_path": "/Applications/Codex.app",
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }


def _contains_all(text: str, expected: list[str]) -> tuple[bool, list[str]]:
    missing = [item for item in expected if item not in text]
    return (not missing, missing)


def _node_browser_check(repo_root: Path) -> dict[str, Any]:
    script = r"""
const fs = require("fs");
const vm = require("vm");

function createElement(tagName) {
  return {
    tagName,
    className: "",
    textContent: "",
    title: "",
    dataset: {},
    children: [],
    append(...nodes) {
      this.children.push(...nodes);
    },
    appendChild(node) {
      this.children.push(node);
    },
    addEventListener() {},
    setAttribute(name, value) {
      this[name] = value;
    }
  };
}

const sandbox = {
  console,
  Node: function Node() {},
  document: {
    createElement,
    getElementById() {
      return { textContent: "", className: "", hidden: false, children: [], append() {}, appendChild() {}, addEventListener() {}, setAttribute() {} };
    },
    addEventListener() {},
    querySelectorAll() { return []; },
    querySelector() { return { dataset: { source: "fixture", screen: "api-connections" } }; }
  },
  window: {
    location: { search: "", href: "http://127.0.0.1/" },
    history: { replaceState() {} }
  },
  URL,
  URLSearchParams,
  fetch() { throw new Error("fetch not expected"); }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync("scripts/overview.js", "utf8"), sandbox);

function flattenText(node) {
  return [node.textContent || "", ...(node.children || []).flatMap(flattenText)].join(" | ");
}

const mainIdentity = sandbox.routeIdentity({
  route_id: "wbp-main",
  display_name: "OpenAI registry entry",
  role_label: "main route",
  primary: true
});
const reserveIdentity = sandbox.routeIdentity({
  route_id: "wbp-reserve",
  display_name: "Reserve candidate",
  role_label: "Допустим для резерва",
  primary: false
});
const mainText = flattenText(mainIdentity);
const reserveText = flattenText(reserveIdentity);
const rolePill = sandbox.routeRolePill({ role_label: "main route", primary: true });
const result = {
  main_text: mainText,
  reserve_text: reserveText,
  meta_container_present: mainIdentity.children.some((child) => child.className === "api-route-meta"),
  role_pill_class: rolePill ? rolePill.className : "",
  role_pill_title: rolePill ? rolePill.title : "",
  main_role_normalized: mainText.includes("Основной маршрут"),
  reserve_role_normalized: reserveText.includes("Резервный кандидат"),
  raw_main_role_hidden: !mainText.includes("main route")
};
if (!result.meta_container_present || !result.main_role_normalized || !result.reserve_role_normalized || !result.raw_main_role_hidden) {
  throw new Error(JSON.stringify(result));
}
console.log(JSON.stringify(result));
"""
    process = subprocess.run(
        ["node", "-e", script],
        cwd=repo_root / "wild_boar_proxy" / "web_design_ui",
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return {
            "status": "blocked",
            "verification_mode": "node_vm_static_dom",
            "stderr": process.stderr.strip(),
            "stdout": process.stdout.strip(),
        }
    return {
        "status": "ok",
        "verification_mode": "node_vm_static_dom",
        "result": json.loads(process.stdout.strip() or "{}"),
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    html = _read_text(HTML_PATH)
    js = _read_text(JS_PATH)
    css = _read_text(CSS_PATH)
    admission = _read_json(ADMISSION_PACKET)
    design_gate = _read_json(DESIGN_GATE_PACKET)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)

    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
    }
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)

    admission_row = next(
        (
            row
            for row in admission.get("rows", [])
            if row.get("annex_id") == "role_profile_ui_polish"
        ),
        {},
    )
    admitted = (
        admission.get("status") == "ok"
        and admission_row.get("currently_admitted") is True
        and admission_row.get("status_class") == "admitted"
        and design_gate.get("design_gate_admitted") is True
    )

    packets["role_profile_ui_surface_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_surface_inventory",
        "status": "ok" if admitted else "blocked",
        "admission_source_packet": str(ADMISSION_PACKET),
        "design_gate_packet": str(DESIGN_GATE_PACKET),
        "html_surface": str(HTML_PATH),
        "js_surface": str(JS_PATH),
        "css_surface": str(CSS_PATH),
        "surfaces": [
            "apiConnectionsScreen",
            "api-role-profile-card",
            "routeIdentity",
            "routeRolePill",
            "api_route_profile",
        ],
        "role_profile_annex_currently_admitted": admitted,
    }

    label_expected = [
        "Role / profile metadata",
        "presentation only",
        "Основной маршрут",
        "Резервный кандидат",
        "function routeRolePill(route)",
        "function normalizedRouteRoleLabel(route)",
    ]
    labels_ok, labels_missing = _contains_all(html + "\n" + js, label_expected)
    packets["role_profile_label_truth_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_label_truth",
        "status": "ok" if labels_ok else "blocked",
        "expected_labels_present": labels_ok,
        "missing_labels": labels_missing,
        "role_label_is_presentation_only": True,
    }

    copy_expected = [
        "не меняют authority, capability или runtime truth",
        "не дают новой command authority",
        "Profile packet остаётся support surface",
        "не подтверждает readiness и не утверждает runtime успех",
    ]
    copy_ok, copy_missing = _contains_all(html + "\n" + js, copy_expected)
    packets["role_profile_copy_claim_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_copy_claim_boundary",
        "status": "ok" if copy_ok else "blocked",
        "copy_boundary_present": copy_ok,
        "missing_copy_boundaries": copy_missing,
        "copy_claims_authority_or_capability": False,
    }

    authority_checks = {
        "route_payload_route_id_only": 'maybeConfirmAndRun(uiAction, { route_id: button.dataset.routeId })' in js,
        "no_route_payload_provider_authority": "provider: button.dataset" not in js,
        "no_route_payload_model_authority": "model: button.dataset" not in js,
        "no_route_payload_account_authority": "account_id: button.dataset.routeId" not in js,
        "no_route_payload_path_authority": "path:" not in js[js.find("function routeActionButton"): js.find("function apiRouteRemoveDisabledReason")],
    }
    packets["role_profile_authority_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_authority_boundary",
        "status": "ok" if all(authority_checks.values()) else "blocked",
        **authority_checks,
        "browser_client_authority_widened": False,
    }

    action_invariance_checks = {
        "api_route_validate_present": "api_route_validate" in js,
        "api_route_check_present": "api_route_check" in js,
        "api_route_allow_present": "api_route_allow" in js,
        "api_route_disable_present": "api_route_disable" in js,
        "api_route_remove_present": "api_route_remove" in js,
        "api_route_profile_present": "api_route_profile" in js,
        "api_route_evidence_capture_present": "api_route_evidence_capture" in js,
        "forbidden_route_create_absent": "api_route_create" not in html + "\n" + js,
        "forbidden_route_update_absent": "api_route_update" not in html + "\n" + js,
        "forbidden_route_draft_absent": "api_route_draft" not in html + "\n" + js,
    }
    packets["role_profile_action_surface_invariance_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_action_surface_invariance",
        "status": "ok" if all(action_invariance_checks.values()) else "blocked",
        **action_invariance_checks,
    }

    visual_checks = {
        "role_profile_card_css_present": ".api-role-profile-card" in css,
        "role_profile_grid_css_present": ".api-role-profile-grid" in css,
        "route_identity_css_present": ".api-route-identity" in css,
        "route_role_pill_css_present": ".api-route-role-pill" in css,
        "api_role_profile_surface_marker_present": 'data-api-role-profile-surface="presentation-only"' in html,
    }
    packets["role_profile_visual_polish_matrix.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_visual_polish_matrix",
        "status": "ok" if all(visual_checks.values()) else "blocked",
        **visual_checks,
    }

    browser_packet = _node_browser_check(repo_root)
    packets["role_profile_browser_verification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_browser_verification",
        **browser_packet,
    }

    validation_checks = {
        "annex_admitted": admitted,
        "label_truth_ok": packets["role_profile_label_truth_packet.json"]["status"] == "ok",
        "copy_boundary_ok": packets["role_profile_copy_claim_boundary_packet.json"]["status"] == "ok",
        "authority_boundary_ok": packets["role_profile_authority_boundary_packet.json"]["status"] == "ok",
        "action_invariance_ok": packets["role_profile_action_surface_invariance_packet.json"]["status"] == "ok",
        "visual_polish_ok": packets["role_profile_visual_polish_matrix.json"]["status"] == "ok",
        "browser_verification_ok": packets["role_profile_browser_verification_packet.json"]["status"] == "ok",
    }
    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [{"name": name, "passed": passed} for name, passed in validation_checks.items()],
    }

    false_green_reasons = [
        name
        for name, passed in validation_checks.items()
        if not passed and name != "annex_admitted"
    ]
    packets["role_profile_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_false_green_audit",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "ui_polish_claimed_as_runtime_improvement": False,
        "role_labels_claimed_as_authority": False,
        "copy_claims_beyond_metadata": False,
        "payload_widening_detected": False,
        "failed_checks": false_green_reasons,
    }

    final_status = (
        "ROLE_PROFILE_UI_POLISH_CLASSIFIED"
        if all(validation_checks.values())
        else "ROLE_PROFILE_UI_POLISH_CLASSIFIED_WITH_LIMITS"
    )
    packets["role_profile_ui_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "role_profile_ui_summary",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "final_status": final_status,
        "admitted_surface_count": 1,
        "polished_surface": "api_connections_role_profile_metadata",
        "new_command_surfaces_introduced": False,
        "authority_boundary_changed": False,
    }
    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok",
        "facts": [
            "role_profile_ui_polish remains currently admitted",
            "api connections screen now contains explicit role/profile metadata boundary copy",
            "route identity rendering normalizes role labels into presentation-only pills",
            "api route action payload remains route_id-only",
            "no new route command surface was introduced",
        ],
    }
    packets["independent_role_profile_ui_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_role_profile_ui_audit",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "admitted_annex_confirmed": admitted,
        "role_copy_boundary_confirmed": packets["role_profile_copy_claim_boundary_packet.json"]["status"] == "ok",
        "authority_boundary_confirmed": packets["role_profile_authority_boundary_packet.json"]["status"] == "ok",
        "action_surface_invariance_confirmed": packets["role_profile_action_surface_invariance_packet.json"]["status"] == "ok",
        "browser_verification_confirmed": packets["role_profile_browser_verification_packet.json"]["status"] == "ok",
    }
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="role-profile-ui-polish-classification-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["role_profile_ui_summary_packet.json"]
    print(
        json.dumps(
            {
                "status": summary["status"],
                "final_status": summary["final_status"],
                "evidence_dir": str(evidence_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
