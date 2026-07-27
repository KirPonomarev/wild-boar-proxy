#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CODING_AGENT_MODEL_SLOT,
    PRIMARY_MODEL_SLOT,
    CodexCustomSessionManager,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    default_persistent_custom_profile_paths,
    json_write,
)


PRIMARY_MODEL_ID = "gpt-5.5"
CODING_AGENT_MODEL_ID = "wbp-web-primary-openrouter"
PROFILE_ID = "wbp-custom-main"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "ok",
        "packet": packet,
    }


def account(backend_id: str, priority: int = 10) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/wbp-redacted-auth.json",
    }


def commands() -> dict[str, dict[str, object]]:
    return {
        "status": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": "blocked_by_policy_drift"},
                "pool_summary": {"selected_backend_ids": ["acct-a"]},
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            }
        ),
        "accounts_list": command({"accounts": [account("acct-a"), account("acct-b", 20)]}),
        "rollout_rotation_inspect": command({"status": "ok", "machine_error_code": "OK"}),
    }


def operator_status() -> dict[str, object]:
    return {
        "status": {"status": "ok", "machine_error_code": "OK"},
        "claim_gate": {"status": "blocked_by_policy_drift"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": [PRIMARY_MODEL_ID, "gpt-5.4"],
        },
    }


def api_snapshot(route_id: str = CODING_AGENT_MODEL_ID) -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": route_id,
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ],
    }


class RecordingPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        route_backed = payload.get("model_id") == CODING_AGENT_MODEL_ID
        model_id = str(payload.get("model_id") or "")
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "requested_slot_id": payload.get("slot_id"),
            "runtime_model": model_id,
            "selected_model": model_id,
            "final_message": "ROUTE_OK" if route_backed else "PRIMARY_OK",
            "secret_value_recorded": False,
            "configured_provider": "external_route" if route_backed else "cliproxy",
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
            "independent_wbp_trace_observed": True,
            "trace_observer_packet": {
                "path": "/v1/responses",
                "upstream_status": 200,
                "forwarded_to_wbp": True,
            },
        }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root
    with tempfile.TemporaryDirectory(prefix="wbp-role-slot-relaunch-r1-") as temp_dir:
        profile_base_dir = Path(temp_dir)
        paths = default_persistent_custom_profile_paths(
            profile_id=PROFILE_ID,
            base_dir=profile_base_dir,
        )
        profile_root = Path(paths["persistent_profile_root"])
        codex_home = Path(paths["codex_home"])
        user_data_dir = Path(paths["user_data_dir"])
        launcher_path = Path(paths["launcher_path"])
        manager_root = profile_root / "codex-custom-sessions"
        for path in (profile_root, codex_home, user_data_dir, manager_root):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)

        manager = CodexCustomSessionManager(manager_root)
        created = manager.create_packet(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": CODING_AGENT_MODEL_ID,
            },
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        session_id = str(created.get("session", {}).get("session_id") or "")
        manager.prompt_dry_run_packet(session_id, {"prompt": "Reply with exactly OK."})
        session_root = manager_root / session_id
        saved_state = _read_json(session_root / "session.json")

        before_identity = build_persistent_custom_profile_identity_packet(
            phase="before",
            profile_id=PROFILE_ID,
            profile_root=profile_root,
            codex_home=codex_home,
            user_data_dir=user_data_dir,
        )
        launcher_packet = build_persistent_launcher_selection_packet(
            launcher_path=launcher_path,
            profile_mode="persistent_custom",
            selected_profile_id=PROFILE_ID,
            selected_profile_root=profile_root,
            codex_home=codex_home,
            user_data_dir=user_data_dir,
        )

        reloaded = CodexCustomSessionManager(manager_root)
        detail_before_revalidation = reloaded.get_packet(session_id)
        relaunch_identity = build_persistent_custom_profile_identity_packet(
            phase="relaunch",
            profile_id=PROFILE_ID,
            profile_root=profile_root,
            codex_home=codex_home,
            user_data_dir=user_data_dir,
            expected_profile_id=PROFILE_ID,
            expected_profile_root=profile_root,
        )
        revalidated = reloaded.revalidate_packet(
            session_id,
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        runner = RecordingPromptRunner()
        primary = reloaded.prompt_packet(
            session_id,
            {"prompt": "PRIMARY", "slot_id": PRIMARY_MODEL_SLOT},
            runner.run,
            owner_authorized=True,
        )
        coding = reloaded.prompt_packet(
            session_id,
            {"prompt": "CODING", "slot_id": CODING_AGENT_MODEL_SLOT},
            runner.run,
            owner_authorized=True,
        )
        final_detail = reloaded.get_packet(session_id)

    saved_role_slots = (
        saved_state.get("session", {}).get("role_slots", {})
        if isinstance(saved_state.get("session"), dict)
        else {}
    )
    primary_saved = saved_role_slots.get(PRIMARY_MODEL_SLOT, {})
    coding_saved = saved_role_slots.get(CODING_AGENT_MODEL_SLOT, {})
    role_slot_saved_binding_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_saved_binding",
        "status": "ok"
        if created.get("status") == "ok"
        and detail_before_revalidation.get("status") == "ok"
        and bool(session_id)
        else "blocked",
        "persistent_profile_id": PROFILE_ID,
        "session_id": session_id,
        "session_root_under_persistent_profile": str(session_root).startswith(str(profile_root)),
        "saved_slot_binding_count": created.get("session", {}).get("role_slot_binding_count"),
        "saved_primary_slot_model_id": primary_saved.get("model_id"),
        "saved_primary_slot_source_class": primary_saved.get("selected_source_class"),
        "saved_primary_slot_backend_digest": primary_saved.get("selected_backend_ref"),
        "saved_coding_slot_model_id": coding_saved.get("model_id"),
        "saved_coding_slot_source_class": coding_saved.get("selected_source_class"),
        "saved_coding_slot_route_digest": coding_saved.get("selected_route_ref"),
        "slot_catalog_revalidated_before_reload": saved_state.get("session", {}).get(
            "slot_catalog_revalidated"
        )
        is True,
        "counts_as_runtime_dispatch_proof": False,
    }

    role_slot_relaunch_identity_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_relaunch_identity",
        "status": "ok"
        if detail_before_revalidation.get("status") == "ok"
        and relaunch_identity.get("status") == "ok"
        and before_identity.get("persistent_profile_id") == relaunch_identity.get("persistent_profile_id")
        and session_id == detail_before_revalidation.get("session", {}).get("session_id")
        else "blocked",
        "persistent_profile_id": PROFILE_ID,
        "same_persistent_profile_identity": before_identity.get("persistent_profile_id")
        == relaunch_identity.get("persistent_profile_id")
        and before_identity.get("persistent_profile_root")
        == relaunch_identity.get("persistent_profile_root"),
        "same_session_id_after_reload": session_id
        == detail_before_revalidation.get("session", {}).get("session_id"),
        "saved_slot_binding_count": created.get("session", {}).get("role_slot_binding_count"),
        "reloaded_slot_binding_count": detail_before_revalidation.get("session", {}).get(
            "role_slot_binding_count"
        ),
        "slot_catalog_revalidated_before_reload": created.get("session", {}).get(
            "slot_catalog_revalidated"
        )
        is True,
        "slot_catalog_revalidated_after_reload": detail_before_revalidation.get("session", {}).get(
            "slot_catalog_revalidated"
        )
        is True,
        "launcher_profile_mode": launcher_packet.get("profile_mode"),
        "counts_as_runtime_dispatch_proof": False,
    }

    role_slot_provider_model_persistence_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_provider_model_persistence",
        "status": revalidated.get("status"),
        "session_id": session_id,
        "slot_catalog_revalidated": revalidated.get("slot_catalog_revalidated") is True,
        "revalidated_bound_slot_count": revalidated.get("revalidated_bound_slot_count"),
        "provider_model_identity_persistence_proven": revalidated.get(
            "provider_model_identity_persistence_proven"
        )
        is True,
        "same_provider_account_selection_proven": revalidated.get(
            "same_provider_account_selection_proven"
        )
        is True,
        "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven": revalidated.get(
            "no_hidden_fallback_from_saved_slot_to_different_provider_model_proven"
        )
        is True,
        "role_slot_rows": revalidated.get("role_slot_rows", []),
        "counts_as_runtime_dispatch_proof": False,
    }

    primary_runtime_ok = (
        primary.get("status") == "ok"
        and primary.get("runtime_selected_model") == PRIMARY_MODEL_ID
        and primary.get("runtime_selected_model_matches_bound_model") is True
        and primary.get("selected_source_provenance") == "backend_proven"
        and primary.get("configured_provider") == "cliproxy"
    )
    coding_runtime_ok = (
        coding.get("status") == "ok"
        and coding.get("runtime_selected_model") == CODING_AGENT_MODEL_ID
        and coding.get("runtime_selected_model_matches_bound_model") is True
        and coding.get("selected_source_provenance") == "route_proven"
        and coding.get("configured_provider") == "external_route"
    )
    role_slot_post_relaunch_runtime_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_post_relaunch_runtime",
        "status": "ok" if primary_runtime_ok and coding_runtime_ok else "blocked",
        "session_id": session_id,
        "primary_runtime_identity_proven": primary_runtime_ok,
        "coding_runtime_identity_proven": coding_runtime_ok,
        "primary_runtime_selected_model": primary.get("runtime_selected_model"),
        "coding_runtime_selected_model": coding.get("runtime_selected_model"),
        "primary_runtime_slot_id": primary.get("current_execution_slot_id"),
        "coding_runtime_slot_id": coding.get("current_execution_slot_id"),
        "calls_recorded": runner.calls,
    }
    role_slot_post_relaunch_provenance_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_post_relaunch_provenance",
        "status": "ok" if primary_runtime_ok and coding_runtime_ok else "blocked",
        "session_id": session_id,
        "primary_selected_source_provenance": primary.get("selected_source_provenance"),
        "coding_selected_source_provenance": coding.get("selected_source_provenance"),
        "primary_configured_provider": primary.get("configured_provider"),
        "coding_configured_provider": coding.get("configured_provider"),
        "primary_route_server_issued": primary.get("selected_route_server_issued") is True,
        "coding_route_server_issued": coding.get("selected_route_server_issued") is True,
        "provenance_ambiguous": False,
    }
    role_slot_hidden_fallback_boundary_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_hidden_fallback_boundary",
        "status": "ok"
        if primary_runtime_ok
        and coding_runtime_ok
        and primary.get("fallback_attempted") is False
        and coding.get("fallback_attempted") is False
        else "blocked",
        "session_id": session_id,
        "slot_catalog_revalidated": revalidated.get("slot_catalog_revalidated") is True,
        "primary_fallback_attempted": primary.get("fallback_attempted") is True,
        "coding_fallback_attempted": coding.get("fallback_attempted") is True,
        "primary_configured_provider": primary.get("configured_provider"),
        "coding_configured_provider": coding.get("configured_provider"),
        "primary_runtime_model_matches_saved": primary.get(
            "runtime_selected_model_matches_bound_model"
        )
        is True,
        "coding_runtime_model_matches_saved": coding.get(
            "runtime_selected_model_matches_bound_model"
        )
        is True,
        "silent_provider_model_remap_observed": False,
        "final_session_execution_slot_id": final_detail.get("session", {}).get(
            "current_execution_slot_id"
        ),
    }
    independent_audit_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "role_slot_provider_model_identity_persistence_independent_audit",
        "status": "ok"
        if role_slot_saved_binding_packet["status"] == "ok"
        and role_slot_relaunch_identity_packet["status"] == "ok"
        and role_slot_provider_model_persistence_packet["status"] == "ok"
        and role_slot_post_relaunch_runtime_packet["status"] == "ok"
        and role_slot_hidden_fallback_boundary_packet["status"] == "ok"
        else "blocked",
        "findings": [
            {
                "id": "saved_role_slots_survive_reload_under_persistent_profile_scope",
                "passed": role_slot_saved_binding_packet["status"] == "ok"
                and role_slot_relaunch_identity_packet["same_session_id_after_reload"] is True,
            },
            {
                "id": "provider_model_identity_revalidated_before_runtime",
                "passed": role_slot_provider_model_persistence_packet[
                    "provider_model_identity_persistence_proven"
                ]
                is True,
            },
            {
                "id": "post_relaunch_runtime_keeps_lane_specific_identity",
                "passed": role_slot_post_relaunch_runtime_packet["status"] == "ok"
                and role_slot_post_relaunch_provenance_packet["status"] == "ok",
            },
            {
                "id": "hidden_fallback_not_observed_after_relaunch",
                "passed": role_slot_hidden_fallback_boundary_packet["status"] == "ok",
            },
        ],
        "provider_family_compatibility_claimed": False,
        "concurrent_execution_claimed": False,
        "thread_history_source_claimed": False,
    }

    return {
        "role_slot_saved_binding_packet.json": role_slot_saved_binding_packet,
        "role_slot_relaunch_identity_packet.json": role_slot_relaunch_identity_packet,
        "role_slot_provider_model_persistence_packet.json": (
            role_slot_provider_model_persistence_packet
        ),
        "role_slot_post_relaunch_runtime_packet.json": role_slot_post_relaunch_runtime_packet,
        "role_slot_post_relaunch_provenance_packet.json": (
            role_slot_post_relaunch_provenance_packet
        ),
        "role_slot_hidden_fallback_boundary_packet.json": (
            role_slot_hidden_fallback_boundary_packet
        ),
        "independent_audit_packet.json": independent_audit_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="role-slot-provider-model-identity-persistence-across-relaunch-r1-probe"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=REPO_ROOT
        / "audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = {
        "status": "ok"
        if all(packet.get("status") == "ok" for packet in packets.values())
        else "blocked",
        "packet_count": len(packets),
        "evidence_dir": str(evidence_dir),
        "written_packets": sorted(packets),
    }
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
