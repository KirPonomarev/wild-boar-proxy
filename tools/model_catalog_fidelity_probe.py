#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate model catalog fidelity evidence packets without live calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_model_catalog_fidelity_packets,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if process.returncode != 0:
        return process.stdout.strip() or process.stderr.strip()
    return process.stdout.strip()


def operator_status() -> dict[str, Any]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.5",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "model_ids": [
                "gpt-5.5",
                "gpt-5.4",
                "gpt-5.5",
                "direct-mistral-devstral-2512",
            ],
            "server_issued": True,
        },
    }


def api_snapshot() -> dict[str, Any]:
    return {
        "routes": [
            {
                "route_id": "wbp:deepseek-max",
                "enabled": True,
                "secret_ref": "DEEPSEEK_API_KEY",
                "upstream_model": "deepseek-max",
                "display_name": "DeepSeek Max",
            },
            {
                "route_id": "native-looking-external",
                "enabled": True,
                "secret_ref": "EXTERNAL_API_KEY",
                "upstream_model": "provider/native-looking",
                "display_name": "External Native Looking",
            },
            {
                "route_id": "wbp-disabled-route",
                "enabled": False,
                "secret_ref": "DISABLED_SECRET",
            },
        ]
    }


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def write_packet(evidence_dir: Path, name: str, payload: dict[str, Any]) -> None:
    (evidence_dir / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    branch = run_text(repo_root, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    current_write_surfaces = [
        "wild_boar_proxy/codex_model_registry.py",
        "tests/test_codex_model_registry.py",
        "tools/model_catalog_fidelity_probe.py",
        str(evidence_dir.relative_to(repo_root)),
    ]
    raw_dirty = [
        line
        for line in run_text(repo_root, ["git", "status", "--short"]).splitlines()
        if line.strip()
    ]
    dirty = [
        line
        for line in raw_dirty
        if not any(surface in line for surface in current_write_surfaces)
    ]
    fidelity_packets = build_model_catalog_fidelity_packets(
        operator_status(),
        api_snapshot=api_snapshot(),
        measurement_packet_present=False,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": packet(
            "sync_gate",
            branch=branch,
            head=head,
            native_launch_attempted=False,
            external_provider_live_call_attempted=False,
            model_availability_smoke_attempted=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            pre_existing_dirty_paths=dirty,
            current_contour_relies_on_historical_dirty_paths=False,
            current_contour_stages_historical_dirty_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=current_write_surfaces,
            native_profile_write_surface=False,
            original_codex_write_surface=False,
            live_route_write_surface=False,
        ),
        "version_pinning_packet.json": packet(
            "version_pinning",
            wbp_git_commit=head,
            python_version=sys.version.split()[0],
            model_catalog_fidelity_schema_version=1,
            provider_endpoint_version_status="not_used_by_this_contour",
            adapter_matrix_version_status="not_used_by_this_contour",
        ),
        **fidelity_packets,
    }
    summary = packets["model_catalog_fidelity_matrix.json"]
    packets["model_catalog_fidelity_summary_packet.json"] = packet(
        "model_catalog_fidelity_summary",
        status=summary.get("status", "blocked"),
        final_status=summary.get("target_status", "WBP_MODEL_CATALOG_FIDELITY_CLASSIFIED"),
        codex_native_lane_status=packets["codex_native_model_lane_packet.json"].get("status"),
        wbp_api_lane_status=packets["wbp_api_model_lane_packet.json"].get("status"),
        display_metadata_is_runtime_truth=False,
        catalog_registry_truth_is_runtime_binding_truth=False,
        runtime_binding_truth_is_capability_proof=False,
        runtime_truth_boundary_is_capability_proof=False,
        model_availability_proven=False,
        native_app_proven=False,
        external_provider_live_proven=False,
        direct_egress_absence_proven=False,
        final_e2e_proven=False,
    )
    return packets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        write_packet(evidence_dir, name, payload)
    summary = packets["model_catalog_fidelity_summary_packet.json"]
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
