"""Backend-only overview action runner for the desktop HTML UI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from wild_boar_proxy.desktop_ui.command_adapter import AdapterResult, Runner, run_command
from wild_boar_proxy.desktop_ui.live_overview import write_live_overview_payload


SOURCE_ID = "ui_desktop_html_overview_action_runner"
DEFAULT_SNAPSHOT_PATH = Path("wild_boar_proxy/desktop_ui/live/overview_live_snapshot.json")


@dataclass(frozen=True)
class OverviewActionSpec:
    action_id: str
    command_id: str
    label: str
    confirmation_required: bool
    post_action_refresh: tuple[str, ...]
    claim_scope: str
    warning: str


ACTION_SPECS = {
    "switch_stable": OverviewActionSpec(
        action_id="switch_stable",
        command_id="mode.set.stable",
        label="Switch Stable",
        confirmation_required=True,
        post_action_refresh=("status", "mode.get"),
        claim_scope="desired_mode_request_plus_refreshed_runtime_readout",
        warning="desired stable does not prove healthy stable",
    ),
    "switch_managed": OverviewActionSpec(
        action_id="switch_managed",
        command_id="mode.set.managed",
        label="Switch Managed",
        confirmation_required=True,
        post_action_refresh=("status", "mode.get", "healthcheck"),
        claim_scope="desired_mode_request_plus_refreshed_runtime_readout",
        warning="desired managed does not prove managed health",
    ),
    "run_sync": OverviewActionSpec(
        action_id="run_sync",
        command_id="sync",
        label="Run Managed Sync",
        confirmation_required=True,
        post_action_refresh=("status", "accounts.list", "mode.get"),
        claim_scope="sync_command_result_plus_refreshed_status_account_readout",
        warning="sync success is not full runtime proof",
    ),
    "launch_client": OverviewActionSpec(
        action_id="launch_client",
        command_id="launch.client",
        label="Launch Client",
        confirmation_required=True,
        post_action_refresh=("status",),
        claim_scope="bounded_host_client_dispatch_truth_only",
        warning="launch success is not host-client session success",
    ),
    "run_smoke": OverviewActionSpec(
        action_id="run_smoke",
        command_id="launch.smoke",
        label="Smoke Test",
        confirmation_required=True,
        post_action_refresh=("status", "healthcheck"),
        claim_scope="bounded_runtime_smoke_evidence_plus_refreshed_status",
        warning="smoke does not prove pilot readiness",
    ),
}


DEFERRED_ACTION_IDS = {
    "stable_repair_dry_run",
    "stable_repair_apply",
    "accounts_onboard",
    "accounts_validate",
    "accounts_promote",
    "accounts_demote",
    "accounts_hold",
    "accounts_release",
    "accounts_retire",
    "diagnostics_export",
    "policy_stage_set",
    "rollout_stage_prove",
    "rollout_stage_advance",
    "rollout_evidence_capture",
    "stable_target_switch",
}


RefreshWriter = Callable[[Path], Mapping[str, Any]]


def run_overview_action(
    action_id: str,
    *,
    confirmed: bool = False,
    runner: Runner | None = None,
    timeout_seconds: float = 30.0,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    refresh_writer: RefreshWriter | None = None,
) -> dict[str, Any]:
    spec = ACTION_SPECS.get(action_id)
    if spec is None:
        return _blocked_packet(action_id, "ACTION_DEFERRED" if action_id in DEFERRED_ACTION_IDS else "ACTION_FORBIDDEN")
    if spec.confirmation_required and not confirmed:
        return _blocked_packet(action_id, "CONFIRMATION_REQUIRED", spec=spec)

    kwargs: dict[str, Any] = {"timeout_seconds": timeout_seconds}
    if runner is not None:
        kwargs["runner"] = runner
    result = run_command(spec.command_id, **kwargs)
    refresh = _run_refresh(snapshot_path, runner=runner, timeout_seconds=timeout_seconds, refresh_writer=refresh_writer)
    action_ok = result.adapter_status == "ok" and refresh["status"] == "ok"
    machine_error_code = _machine_error_code(result, refresh, action_ok)
    human_message = _human_message(result, refresh, action_ok)
    return {
        "source": SOURCE_ID,
        "action_id": spec.action_id,
        "command_id": spec.command_id,
        "status": "ok" if action_ok else "error",
        "adapter_status": result.adapter_status,
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "confirmation_required": spec.confirmation_required,
        "confirmed": confirmed,
        "claim_scope": spec.claim_scope,
        "warning": spec.warning,
        "changed_files": _changed_files(result),
        "post_action_refresh": list(spec.post_action_refresh),
        "post_action_refresh_status": refresh["status"],
        "post_action_refresh_error": refresh["error"],
        "snapshot_written": refresh["snapshot_written"],
        "snapshot_path": _snapshot_path_for_packet(snapshot_path),
        "next_action": "none" if action_ok else "user_action",
        "operator_action": "none" if action_ok else "user_action",
    }


def list_action_specs() -> dict[str, OverviewActionSpec]:
    return dict(ACTION_SPECS)


def list_deferred_action_ids() -> set[str]:
    return set(DEFERRED_ACTION_IDS)


def _blocked_packet(action_id: str, machine_error_code: str, *, spec: OverviewActionSpec | None = None) -> dict[str, Any]:
    return {
        "source": SOURCE_ID,
        "action_id": action_id,
        "command_id": spec.command_id if spec else "",
        "status": "error",
        "adapter_status": "not_executed",
        "machine_error_code": machine_error_code,
        "human_message": _blocked_message(machine_error_code),
        "confirmation_required": spec.confirmation_required if spec else False,
        "confirmed": False,
        "claim_scope": spec.claim_scope if spec else "none",
        "warning": spec.warning if spec else "",
        "changed_files": [],
        "post_action_refresh": list(spec.post_action_refresh) if spec else [],
        "post_action_refresh_status": "not_run",
        "post_action_refresh_error": "",
        "snapshot_written": False,
        "snapshot_path": "",
        "next_action": "user_action",
        "operator_action": "user_action",
    }


def _blocked_message(machine_error_code: str) -> str:
    if machine_error_code == "CONFIRMATION_REQUIRED":
        return "Explicit confirmation is required before this action can run."
    if machine_error_code == "ACTION_DEFERRED":
        return "This action is deferred to a later UI contour."
    return "This action is not admitted for the overview action runner."


def _run_refresh(
    snapshot_path: Path,
    *,
    runner: Runner | None,
    timeout_seconds: float,
    refresh_writer: RefreshWriter | None,
) -> dict[str, Any]:
    try:
        if refresh_writer is not None:
            refresh_writer(snapshot_path)
        else:
            write_live_overview_payload(snapshot_path, runner=runner, timeout_seconds=timeout_seconds)
    except Exception as exc:  # pragma: no cover - defensive boundary.
        return {"status": "error", "snapshot_written": False, "error": str(exc)}
    return {"status": "ok", "snapshot_written": True, "error": ""}


def _machine_error_code(result: AdapterResult, refresh: Mapping[str, Any], action_ok: bool) -> str:
    if action_ok:
        return (result.raw_packet or {}).get("machine_error_code", "OK")
    if result.adapter_status == "integration_failure":
        return result.error_code
    if result.adapter_status == "command_error":
        return (result.raw_packet or {}).get("machine_error_code", "COMMAND_ERROR")
    if refresh["status"] != "ok":
        return "POST_ACTION_REFRESH_FAILED"
    return "ACTION_FAILED"


def _human_message(result: AdapterResult, refresh: Mapping[str, Any], action_ok: bool) -> str:
    if refresh["status"] != "ok":
        return f"Action ran but post-action refresh failed: {refresh['error']}"
    if result.raw_packet and result.raw_packet.get("human_message"):
        return str(result.raw_packet["human_message"])
    if action_ok:
        return "Action completed and post-action refresh succeeded."
    return result.error_message or "Action did not complete successfully."


def _changed_files(result: AdapterResult) -> list[Any]:
    changed = (result.raw_packet or {}).get("changed_files", [])
    return changed if isinstance(changed, list) else []


def _snapshot_path_for_packet(snapshot_path: Path) -> str:
    return snapshot_path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an admitted backend-only desktop overview action.")
    parser.add_argument("action_id")
    parser.add_argument("--confirmed", action="store_true", help="Explicitly confirm a required mutating action.")
    parser.add_argument("--output", type=Path, help="Write action result JSON to this path instead of stdout.")
    parser.add_argument("--snapshot-output", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    packet = run_overview_action(
        args.action_id,
        confirmed=args.confirmed,
        timeout_seconds=args.timeout,
        snapshot_path=args.snapshot_output,
    )
    rendered = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
