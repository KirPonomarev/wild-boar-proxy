"""Live overview snapshot provider for the desktop HTML UI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from wild_boar_proxy.desktop_ui.command_adapter import AdapterResult, Runner, run_command


READ_COMMAND_IDS = (
    "status",
    "healthcheck",
    "mode.get",
    "accounts.list",
    "rollout.rotation.inspect",
)

SOURCE_ID = "ui_desktop_html_live_overview_snapshot"


def collect_live_overview_payload(
    *,
    runner: Runner | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    outcomes = {
        command_id: _run_read(command_id, runner=runner, timeout_seconds=timeout_seconds)
        for command_id in READ_COMMAND_IDS
    }
    status_packet = _status_packet(outcomes["status"])
    mode_packet = _mode_packet(outcomes["mode.get"], status_packet)
    accounts_packet = _accounts_packet(outcomes["accounts.list"])
    health_summary = _summary_packet(outcomes["healthcheck"])
    rotation_summary = _rotation_summary(outcomes["rollout.rotation.inspect"])

    state = _overview_state(outcomes, status_packet, mode_packet)
    notice = _notice(outcomes, mode_packet)
    return {
        "source": SOURCE_ID,
        "synthetic": False,
        "live_mode": True,
        "fixture_id": None,
        "fixture_state": state,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "truth_source": "command_adapter",
        "status_packet": status_packet,
        "mode_packet": mode_packet,
        "accounts_packet": accounts_packet,
        "health_summary": health_summary,
        "rotation_summary": rotation_summary,
        "command_outcomes": {
            command_id: _command_outcome(result) for command_id, result in outcomes.items()
        },
        "events": _events(outcomes, mode_packet),
        "notice": notice,
    }


def write_live_overview_payload(
    output_path: Path,
    *,
    runner: Runner | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    payload = collect_live_overview_payload(runner=runner, timeout_seconds=timeout_seconds)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _run_read(command_id: str, *, runner: Runner | None, timeout_seconds: float) -> AdapterResult:
    kwargs: dict[str, Any] = {"timeout_seconds": timeout_seconds}
    if runner is not None:
        kwargs["runner"] = runner
    return run_command(command_id, **kwargs)


def _status_packet(result: AdapterResult) -> dict[str, Any]:
    packet = _base_packet(result)
    raw = result.raw_packet or {}
    for key in ("desired_mode", "effective_mode", "endpoint", "last_error"):
        if key in raw:
            packet[key] = raw[key]
    return packet


def _mode_packet(result: AdapterResult, status_packet: Mapping[str, Any]) -> dict[str, Any]:
    packet = _base_packet(result)
    raw = result.raw_packet or {}
    packet["desired_mode"] = raw.get("desired_mode") or status_packet.get("desired_mode") or "unknown"
    packet["effective_mode"] = raw.get("effective_mode") or status_packet.get("effective_mode") or "unknown"
    packet["mode_mismatch"] = packet["desired_mode"] != packet["effective_mode"]
    return packet


def _accounts_packet(result: AdapterResult) -> dict[str, Any]:
    packet = _base_packet(result)
    raw = result.raw_packet or {}
    summary = raw.get("account_summary")
    if not isinstance(summary, Mapping):
        summary = _derive_account_summary(raw.get("accounts"))
    packet["account_summary"] = dict(summary)
    packet["capacity_model"] = {
        "capacity_target": 20,
        "claim": "capacity_model_only_not_scale_proof",
    }
    return packet


def _derive_account_summary(accounts: Any) -> dict[str, Any]:
    if not isinstance(accounts, list):
        return {
            "active_count": 0,
            "reserve_count": 0,
            "hold_count": 0,
            "problem_count": 0,
            "active_note": "account list unavailable",
            "reserve_note": "unknown",
            "hold_note": "unknown",
            "problem_note": "unknown",
        }
    active = [item for item in accounts if isinstance(item, Mapping) and item.get("pool") == "active"]
    reserve = [item for item in accounts if isinstance(item, Mapping) and item.get("pool") == "reserve"]
    hold = [
        item
        for item in accounts
        if isinstance(item, Mapping) and (item.get("manual_hold") is True or item.get("pool") == "hold")
    ]
    problem = [
        item
        for item in accounts
        if isinstance(item, Mapping) and item.get("status") in {"degraded", "down"}
    ]
    healthy = [
        item
        for item in accounts
        if isinstance(item, Mapping) and item.get("status") == "healthy"
    ]
    return {
        "active_count": len(active),
        "reserve_count": len(reserve),
        "hold_count": len(hold),
        "problem_count": len(problem),
        "healthy_count": len(healthy),
        "degraded_count": sum(1 for item in problem if item.get("status") == "degraded"),
        "down_count": sum(1 for item in problem if item.get("status") == "down"),
        "active_note": "active routing inventory, not scale proof",
        "reserve_note": "reserve pool count",
        "hold_note": "manual hold or hold pool",
        "problem_note": "degraded/down accounts",
    }


def _summary_packet(result: AdapterResult) -> dict[str, Any]:
    packet = _base_packet(result)
    raw = result.raw_packet or {}
    attestation = raw.get("attestation")
    packet["attestation_status"] = "present" if isinstance(attestation, Mapping) else "missing"
    if isinstance(attestation, Mapping):
        packet["attestation_fields_present"] = sorted(attestation.keys())
    return packet


def _rotation_summary(result: AdapterResult) -> dict[str, Any]:
    packet = _base_packet(result)
    raw = result.raw_packet or {}
    rotation_result = raw.get("rotation_evidence_result")
    packet["proof_claim"] = "not_claimed"
    if isinstance(rotation_result, Mapping):
        packet["participation_status"] = rotation_result.get("participation_status", "unknown")
        packet["evidence_status"] = rotation_result.get("evidence_status", "unknown")
    else:
        packet["participation_status"] = "unknown"
        packet["evidence_status"] = "unknown"
    return packet


def _base_packet(result: AdapterResult) -> dict[str, Any]:
    raw = result.raw_packet or {}
    packet = {
        "status": raw.get("status", "error"),
        "exit_code": raw.get("exit_code", 1),
        "human_message": raw.get("human_message") or result.error_message or "Command did not return usable data.",
        "machine_error_code": raw.get("machine_error_code") or result.error_code,
        "changed_files": [],
        "next_action": raw.get("next_action", "stop"),
        "liveness": raw.get("liveness", "unknown"),
        "severity": raw.get("severity", "recoverable"),
        "operator_action": raw.get("operator_action", "user_action"),
        "adapter_status": result.adapter_status,
    }
    if result.adapter_status == "integration_failure":
        packet["status"] = "error"
        packet["liveness"] = "unknown"
        packet["operator_action"] = "user_action"
    return packet


def _command_outcome(result: AdapterResult) -> dict[str, Any]:
    return {
        "command_id": result.command_id,
        "command_class": result.command_class,
        "adapter_status": result.adapter_status,
        "machine_error_code": (result.raw_packet or {}).get("machine_error_code") or result.error_code,
        "error_message": result.error_message,
        "confirmation_level": result.confirmation_level,
    }


def _overview_state(
    outcomes: Mapping[str, AdapterResult],
    status_packet: Mapping[str, Any],
    mode_packet: Mapping[str, Any],
) -> str:
    result = outcomes["status"]
    if result.adapter_status == "integration_failure":
        return "integration-failure"
    if result.adapter_status == "command_error" or status_packet.get("status") == "error":
        return "error"
    liveness = status_packet.get("liveness")
    has_non_status_issue = any(
        command_id != "status" and outcome.adapter_status in {"integration_failure", "command_error"}
        for command_id, outcome in outcomes.items()
    )
    if liveness == "healthy" and (has_non_status_issue or mode_packet.get("mode_mismatch")):
        return "degraded"
    if liveness in {"healthy", "degraded", "down", "stale", "unknown"}:
        return str(liveness)
    return "unknown"


def _notice(outcomes: Mapping[str, AdapterResult], mode_packet: Mapping[str, Any]) -> str:
    failed = [
        command_id
        for command_id, result in outcomes.items()
        if result.adapter_status in {"integration_failure", "command_error"}
    ]
    if mode_packet.get("mode_mismatch"):
        return "Desired and effective modes differ; UI must not show full managed success."
    if failed:
        return f"Live read has visible command issues: {', '.join(failed)}"
    return ""


def _events(outcomes: Mapping[str, AdapterResult], mode_packet: Mapping[str, Any]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for command_id, result in outcomes.items():
        if result.adapter_status == "ok":
            tone = "green"
            icon = "✓"
            message = f"{command_id}: live packet accepted"
        elif result.adapter_status == "command_error":
            tone = "red"
            icon = "!"
            message = f"{command_id}: command error is visible"
        else:
            tone = "red"
            icon = "!"
            message = f"{command_id}: integration failure"
        events.append({"tone": tone, "icon": icon, "message": message, "time": "live read"})
    if mode_packet.get("mode_mismatch"):
        events.append({
            "tone": "amber",
            "icon": "!",
            "message": "Desired mode differs from effective mode",
            "time": "live read",
        })
    return events


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a sanitized desktop UI live overview snapshot.")
    parser.add_argument("--output", type=Path, help="Write snapshot JSON to this path instead of stdout.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-command timeout in seconds.")
    args = parser.parse_args(argv)

    payload = collect_live_overview_payload(timeout_seconds=args.timeout)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
