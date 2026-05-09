"""Backend bridge contract for the desktop HTML overview."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from wild_boar_proxy.desktop_ui.live_overview import write_live_overview_payload
from wild_boar_proxy.desktop_ui.overview_actions import DEFAULT_SNAPSHOT_PATH, run_overview_action


SOURCE_ID = "ui_desktop_html_overview_bridge_contract"
ALLOWED_OPERATION_IDS = {"refresh_overview", "run_overview_action"}
FORBIDDEN_REQUEST_FIELDS = {
    "command",
    "argv",
    "shell",
    "path",
    "state_path",
    "log_path",
    "registry_path",
    "snapshot_path",
    "runtime_file",
    "env",
    "cwd",
}

RefreshWriter = Callable[[Path], Mapping[str, Any]]
ActionRunner = Callable[..., Mapping[str, Any]]


def run_bridge_request(
    request: Mapping[str, Any],
    *,
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH,
    refresh_writer: RefreshWriter | None = None,
    action_runner: ActionRunner | None = None,
) -> dict[str, Any]:
    forbidden = sorted(FORBIDDEN_REQUEST_FIELDS.intersection(request))
    operation_id = request.get("operation_id")
    if forbidden:
        return _error_packet(
            str(operation_id or ""),
            "BRIDGE_REQUEST_FORBIDDEN_FIELD",
            f"Bridge request contains forbidden fields: {', '.join(forbidden)}",
        )
    if not isinstance(operation_id, str) or operation_id not in ALLOWED_OPERATION_IDS:
        return _error_packet(str(operation_id or ""), "BRIDGE_OPERATION_FORBIDDEN", "Bridge operation is not allowlisted.")

    if operation_id == "refresh_overview":
        return _refresh_overview(snapshot_path=snapshot_path, refresh_writer=refresh_writer)
    if operation_id == "run_overview_action":
        action_id = request.get("action_id")
        if not isinstance(action_id, str) or not action_id:
            return _error_packet(operation_id, "BRIDGE_ACTION_ID_REQUIRED", "Bridge action_id is required.")
        confirmed = request.get("confirmed", False) is True
        return _run_action(
            action_id,
            confirmed=confirmed,
            snapshot_path=snapshot_path,
            action_runner=action_runner,
        )
    return _error_packet(operation_id, "BRIDGE_OPERATION_FORBIDDEN", "Bridge operation is not allowlisted.")


def _refresh_overview(
    *,
    snapshot_path: Path,
    refresh_writer: RefreshWriter | None,
) -> dict[str, Any]:
    try:
        if refresh_writer is not None:
            refresh_writer(snapshot_path)
        else:
            write_live_overview_payload(snapshot_path)
    except Exception as exc:  # pragma: no cover - defensive boundary.
        return _error_packet("refresh_overview", "BRIDGE_OPERATION_FAILED", str(exc), snapshot_path=snapshot_path)
    return _packet(
        operation_id="refresh_overview",
        status="ok",
        machine_error_code="OK",
        human_message="Overview snapshot refreshed.",
        snapshot_written=True,
        snapshot_path=snapshot_path,
        action_result=None,
        next_action="none",
        operator_action="none",
    )


def _run_action(
    action_id: str,
    *,
    confirmed: bool,
    snapshot_path: Path,
    action_runner: ActionRunner | None,
) -> dict[str, Any]:
    try:
        if action_runner is not None:
            action_result = dict(action_runner(action_id, confirmed=confirmed, snapshot_path=snapshot_path))
        else:
            action_result = run_overview_action(action_id, confirmed=confirmed, snapshot_path=snapshot_path)
    except Exception as exc:  # pragma: no cover - defensive boundary.
        return _error_packet("run_overview_action", "BRIDGE_OPERATION_FAILED", str(exc), snapshot_path=snapshot_path)

    ok = action_result.get("status") == "ok"
    return _packet(
        operation_id="run_overview_action",
        status="ok" if ok else "error",
        machine_error_code=str(action_result.get("machine_error_code") or ("OK" if ok else "BRIDGE_OPERATION_FAILED")),
        human_message=str(action_result.get("human_message") or "Overview action completed."),
        snapshot_written=bool(action_result.get("snapshot_written")),
        snapshot_path=snapshot_path,
        action_result=action_result,
        next_action=str(action_result.get("next_action") or ("none" if ok else "user_action")),
        operator_action=str(action_result.get("operator_action") or ("none" if ok else "user_action")),
    )


def _error_packet(
    operation_id: str,
    machine_error_code: str,
    human_message: str,
    *,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    return _packet(
        operation_id=operation_id,
        status="error",
        machine_error_code=machine_error_code,
        human_message=human_message,
        snapshot_written=False,
        snapshot_path=snapshot_path,
        action_result=None,
        next_action="user_action",
        operator_action="user_action",
    )


def _packet(
    *,
    operation_id: str,
    status: str,
    machine_error_code: str,
    human_message: str,
    snapshot_written: bool,
    snapshot_path: Path | None,
    action_result: Mapping[str, Any] | None,
    next_action: str,
    operator_action: str,
) -> dict[str, Any]:
    return {
        "source": SOURCE_ID,
        "operation_id": operation_id,
        "status": status,
        "machine_error_code": machine_error_code,
        "human_message": human_message,
        "snapshot_written": snapshot_written,
        "snapshot_path": snapshot_path.as_posix() if snapshot_path else "",
        "action_result": dict(action_result) if action_result else None,
        "next_action": next_action,
        "operator_action": operator_action,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a fixed desktop overview bridge operation.")
    parser.add_argument("--request-json", required=True, help="Bridge request JSON object.")
    parser.add_argument("--output", type=Path, help="Write bridge result JSON to this path instead of stdout.")
    args = parser.parse_args(argv)

    try:
        request = json.loads(args.request_json)
    except json.JSONDecodeError as exc:
        packet = _error_packet("", "BRIDGE_OPERATION_FAILED", f"Bridge request is invalid JSON: {exc.msg}")
    else:
        if not isinstance(request, dict):
            packet = _error_packet("", "BRIDGE_OPERATION_FAILED", "Bridge request JSON must be an object.")
        else:
            packet = run_bridge_request(request)

    rendered = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
