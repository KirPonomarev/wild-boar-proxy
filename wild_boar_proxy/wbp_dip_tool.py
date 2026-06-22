# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .core import packets


WBP_DIP_TOOL_PACKET_KIND = "wbp_dip_working_tool_run"
DEFAULT_ALIAS = "DIP"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_SANDBOX = "danger-full-access"
DEFAULT_CODEX_APP_NAME = "Codex WBP Clean.app"
DEFAULT_ENTRY_EVIDENCE_FILENAME = "mcp-entry-evidence.json"
DEFAULT_CODEX_JSONL_FILENAME = "codex-exec.jsonl"
DEFAULT_LAST_MESSAGE_FILENAME = "last-message.txt"

WBP_DIP_TOOL_OK = "OK"
WBP_DIP_TOOL_DRY_RUN = "WBP_DIP_TOOL_DRY_RUN"
WBP_DIP_TOOL_TASK_REQUIRED = "WBP_DIP_TOOL_TASK_REQUIRED"
WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE = "WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE"
WBP_DIP_TOOL_CODEX_EXEC_FAILED = "WBP_DIP_TOOL_CODEX_EXEC_FAILED"
WBP_DIP_TOOL_DELEGATE_NOT_PROVEN = "WBP_DIP_TOOL_DELEGATE_NOT_PROVEN"
WBP_DIP_TOOL_UNSAFE_PACKET = "WBP_DIP_TOOL_UNSAFE_PACKET"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_array(values: Sequence[str]) -> str:
    return "[" + ",".join(_toml_string(value) for value in values) + "]"


def _toml_inline_table(values: Mapping[str, str]) -> str:
    return (
        "{"
        + ",".join(
            f"{key}={_toml_string(value)}"
            for key, value in sorted(values.items())
            if value
        )
        + "}"
    )


def default_profile_dir(env: Mapping[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    raw = (
        source.get("WBP_PROFILE_DIR")
        or source.get("CODEX_HOME")
        or str(
            Path.home()
            / "Library/Application Support/WildBoarProxy/CodexProfiles/wbp-custom-main"
        )
    )
    return Path(raw).expanduser()


def default_codex_bin(env: Mapping[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    if source.get("WBP_CODEX_BIN"):
        return Path(str(source["WBP_CODEX_BIN"])).expanduser()
    app_path = Path(
        source.get(
            "WBP_CODEX_APP_COPY_PATH",
            str(Path.home() / "Applications" / DEFAULT_CODEX_APP_NAME),
        )
    ).expanduser()
    return app_path / "Contents/Resources/codex"


def default_proof_dir(profile_dir: Path) -> Path:
    return profile_dir / "managed" / "wbp-dip-tool" / _utc_stamp()


def build_delegate_prompt(*, task: str, expected_alias: str) -> str:
    payload = {
        "task": task,
        "expected_alias": expected_alias,
    }
    return (
        "Use only the WBP MCP tool. Do not run shell commands. Do not inspect "
        "files. Call delegate_to_dip exactly once with the JSON arguments below. "
        "Do not answer locally and do not create a Codex sub-agent as DIP. After "
        "the tool returns, answer one concise line with status and any digest "
        "fields returned by the tool.\n\n"
        f"delegate_to_dip arguments JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def build_codex_exec_argv(
    *,
    codex_bin: Path,
    repo_root: Path,
    model: str,
    sandbox: str,
    prompt: str,
    output_jsonl: Path,
    output_last_message: Path,
    profile_dir: Path,
    entry_evidence_file: Path,
    extra_args: Sequence[str] = (),
) -> list[str]:
    env_table = {
        "PYTHONPATH": str(repo_root),
        "WBP_ENTRY_HOOK_EVIDENCE_PATH": str(entry_evidence_file),
        "WBP_PROFILE_DIR": str(profile_dir),
    }
    return [
        str(codex_bin),
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        sandbox,
        "--json",
        "-m",
        model,
        "-o",
        str(output_last_message),
        "-c",
        'mcp_servers.wbp.command="python3"',
        "-c",
        f"mcp_servers.wbp.args={_toml_array(['-m', 'wild_boar_proxy.mcp_delegate'])}",
        "-c",
        f"mcp_servers.wbp.enabled_tools={_toml_array(['delegate_to_dip'])}",
        "-c",
        "mcp_servers.wbp.supports_parallel_tool_calls=false",
        "-c",
        'mcp_servers.wbp.tools.delegate_to_dip.approval_mode="approve"',
        "-c",
        f"mcp_servers.wbp.env={_toml_inline_table(env_table)}",
        *list(extra_args),
        prompt,
    ]


def _iter_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for item in value.values():
            found.extend(_iter_mappings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_iter_mappings(item))
    return found


def _json_mapping_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _structured_packet_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    for field in ("structuredContent", "structured_content"):
        packet = _json_mapping_from_value(mapping.get(field))
        if packet:
            return packet
    result = _json_mapping_from_value(mapping.get("result"))
    for field in ("structuredContent", "structured_content"):
        packet = _json_mapping_from_value(result.get(field))
        if packet:
            return packet
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            item_mapping = _json_mapping_from_value(item)
            packet = _json_mapping_from_value(item_mapping.get("text"))
            if packet:
                return packet
    return {}


def _read_codex_exec_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return events
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            events.append(dict(parsed))
    return events


def _find_delegate_packet(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for event in events:
        for mapping in _iter_mappings(event):
            packet = _structured_packet_from_mapping(mapping)
            if packet.get("packet_kind") == "wbp_mcp_delegate_to_dip_reality":
                return packet
    return {}


def _assistant_response_observed(events: Sequence[Mapping[str, Any]]) -> bool:
    for event in events:
        for mapping in _iter_mappings(event):
            item_type = _safe_text(
                mapping.get("type") or mapping.get("kind") or mapping.get("item_type"),
                limit=80,
            ).casefold()
            role = _safe_text(mapping.get("role") or mapping.get("author"), limit=80).casefold()
            if role == "assistant" or item_type in {"assistant_message", "agent_message", "message"}:
                return True
    return False


def build_wbp_dip_tool_packet(
    *,
    task: str,
    expected_alias: str,
    codex_exit_code: int | None,
    codex_exec_jsonl_file: Path,
    output_last_message_file: Path,
    entry_evidence_file: Path,
    proof_dir: Path,
    dry_run: bool = False,
    codex_executable: bool = True,
    changed_files: Sequence[str] = (),
    secret_values: Sequence[str] = (),
) -> dict[str, Any]:
    task_digest = _sha256_text(task) if task else ""
    events = _read_codex_exec_jsonl(codex_exec_jsonl_file)
    delegate_packet = _find_delegate_packet(events)
    delegate_ok = bool(
        delegate_packet.get("status") == "ok"
        and delegate_packet.get("machine_error_code") == "OK"
        and delegate_packet.get("delegate_to_dip_tool_called") is True
        and delegate_packet.get("api_lane_called") is True
        and delegate_packet.get("route_bound_dispatch_proven") is True
        and delegate_packet.get("fallback_used") is False
        and delegate_packet.get("local_imitation_used") is False
        and delegate_packet.get("raw_backend_details_exposed") is False
        and delegate_packet.get("secret_value_exposed") is False
    )
    assistant_observed = _assistant_response_observed(events) or output_last_message_file.is_file()
    blocking_reasons: list[str] = []
    if not task:
        blocking_reasons.append("task_required")
    if not codex_executable:
        blocking_reasons.append("codex_binary_not_executable")
    if codex_exit_code not in {0, None}:
        blocking_reasons.append("codex_exec_failed")
    if not dry_run and codex_exit_code == 0 and not delegate_ok:
        blocking_reasons.append("delegate_to_dip_not_proven")

    unsafe_payload = {
        "packet_kind": WBP_DIP_TOOL_PACKET_KIND,
        "task_sha256": task_digest,
        "expected_alias": expected_alias,
        "codex_exec_jsonl_sha256": _sha256_file(codex_exec_jsonl_file),
        "output_last_message_sha256": _sha256_file(output_last_message_file),
        "entry_evidence_sha256": _sha256_file(entry_evidence_file),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values),
    )
    if unsafe:
        blocking_reasons.append("unsafe_packet_secret_leak")

    if unsafe:
        machine_error_code = WBP_DIP_TOOL_UNSAFE_PACKET
    elif not task:
        machine_error_code = WBP_DIP_TOOL_TASK_REQUIRED
    elif not codex_executable:
        machine_error_code = WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE
    elif dry_run:
        machine_error_code = WBP_DIP_TOOL_DRY_RUN
    elif codex_exit_code != 0:
        machine_error_code = WBP_DIP_TOOL_CODEX_EXEC_FAILED
    elif delegate_ok:
        machine_error_code = WBP_DIP_TOOL_OK
    else:
        machine_error_code = WBP_DIP_TOOL_DELEGATE_NOT_PROVEN

    ok = machine_error_code in {WBP_DIP_TOOL_OK, WBP_DIP_TOOL_DRY_RUN}
    return {
        "schema_version": 1,
        "packet_kind": WBP_DIP_TOOL_PACKET_KIND,
        "status": "ok" if ok else "error",
        "exit_code": 0 if ok else 1,
        "human_message": (
            "WBP DIP working tool completed through Custom Codex MCP delegate_to_dip."
            if machine_error_code == WBP_DIP_TOOL_OK
            else "WBP DIP working tool dry run prepared."
            if machine_error_code == WBP_DIP_TOOL_DRY_RUN
            else "WBP DIP working tool did not complete a proven delegate_to_dip path."
        ),
        "machine_error_code": machine_error_code,
        "effect": "probe" if dry_run else "mutate",
        "operator_action": "none" if ok else "retry",
        "next_action": "none" if ok else "retry",
        "blocking_reasons": sorted(set(blocking_reasons)),
        "changed_files": list(changed_files),
        "product_ready": False,
        "custom_codex_exec_invoked": bool(not dry_run and codex_executable and task),
        "mcp_delegate_configured": True,
        "delegate_to_dip_tool_call_observed": delegate_packet.get("delegate_to_dip_tool_called") is True,
        "delegate_to_dip_proven": delegate_ok,
        "api_lane_called": delegate_packet.get("api_lane_called") is True,
        "route_bound_dispatch_proven": delegate_packet.get("route_bound_dispatch_proven") is True,
        "fallback_used": delegate_packet.get("fallback_used") is True,
        "local_imitation_used": delegate_packet.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": False,
        "raw_backend_details_exposed": delegate_packet.get("raw_backend_details_exposed") is True,
        "secret_value_exposed": delegate_packet.get("secret_value_exposed") is True,
        "assistant_response_observed": assistant_observed,
        "expected_alias": expected_alias,
        "task_sha256": task_digest,
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
        "codex_exec_exit_code": codex_exit_code,
        "codex_exec_jsonl_file_present": codex_exec_jsonl_file.is_file(),
        "codex_exec_jsonl_sha256": _sha256_file(codex_exec_jsonl_file),
        "output_last_message_file_present": output_last_message_file.is_file(),
        "output_last_message_sha256": _sha256_file(output_last_message_file),
        "entry_evidence_file_present": entry_evidence_file.is_file(),
        "entry_evidence_sha256": _sha256_file(entry_evidence_file),
        "proof_dir_path_recorded": False,
        "codex_exec_jsonl_file_path_recorded": False,
        "output_last_message_file_path_recorded": False,
        "entry_evidence_file_path_recorded": False,
        "delegate_packet_sha256": (
            _sha256_text(
                json.dumps(
                    delegate_packet,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
            if delegate_packet
            else ""
        ),
    }


def _task_from_args(values: Sequence[str]) -> str:
    return " ".join(str(value) for value in values).strip()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wbp_dip")
    parser.add_argument("task", nargs="*")
    parser.add_argument("--alias", default=DEFAULT_ALIAS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sandbox", default=DEFAULT_SANDBOX)
    parser.add_argument("--profile-dir")
    parser.add_argument("--codex-bin")
    parser.add_argument("--cd", dest="repo_root", default=str(Path.cwd()))
    parser.add_argument("--proof-dir")
    parser.add_argument("--output-jsonl")
    parser.add_argument("--output-last-message")
    parser.add_argument("--entry-evidence-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    task = _task_from_args(args.task)
    if not task and not sys.stdin.isatty():
        task = sys.stdin.read().strip()
    task = _safe_text(task, limit=4096)
    expected_alias = _safe_text(args.alias, limit=80) or DEFAULT_ALIAS
    profile_dir = Path(args.profile_dir).expanduser() if args.profile_dir else default_profile_dir()
    proof_dir = Path(args.proof_dir).expanduser() if args.proof_dir else default_proof_dir(profile_dir)
    output_jsonl = (
        Path(args.output_jsonl).expanduser()
        if args.output_jsonl
        else proof_dir / DEFAULT_CODEX_JSONL_FILENAME
    )
    output_last_message = (
        Path(args.output_last_message).expanduser()
        if args.output_last_message
        else proof_dir / DEFAULT_LAST_MESSAGE_FILENAME
    )
    entry_evidence_file = (
        Path(args.entry_evidence_file).expanduser()
        if args.entry_evidence_file
        else proof_dir / DEFAULT_ENTRY_EVIDENCE_FILENAME
    )
    repo_root = Path(args.repo_root).expanduser().resolve()
    codex_bin = Path(args.codex_bin).expanduser() if args.codex_bin else default_codex_bin()
    prompt = build_delegate_prompt(task=task, expected_alias=expected_alias)
    argv_to_run = build_codex_exec_argv(
        codex_bin=codex_bin,
        repo_root=repo_root,
        model=_safe_text(args.model, limit=80) or DEFAULT_MODEL,
        sandbox=_safe_text(args.sandbox, limit=80) or DEFAULT_SANDBOX,
        prompt=prompt,
        output_jsonl=output_jsonl,
        output_last_message=output_last_message,
        profile_dir=profile_dir,
        entry_evidence_file=entry_evidence_file,
    )
    codex_executable = codex_bin.is_file() and os.access(codex_bin, os.X_OK)
    changed_files = [str(output_jsonl), str(output_last_message), str(entry_evidence_file)]
    codex_exit_code: int | None = None
    if args.dry_run:
        dry_packet = build_wbp_dip_tool_packet(
            task=task,
            expected_alias=expected_alias,
            codex_exit_code=None,
            codex_exec_jsonl_file=output_jsonl,
            output_last_message_file=output_last_message,
            entry_evidence_file=entry_evidence_file,
            proof_dir=proof_dir,
            dry_run=True,
            codex_executable=codex_executable,
            changed_files=[],
            secret_values=[task],
        )
        dry_packet.update(
            {
                "planned_codex_exec": True,
                "planned_sandbox": _safe_text(args.sandbox, limit=80) or DEFAULT_SANDBOX,
                "planned_model": _safe_text(args.model, limit=80) or DEFAULT_MODEL,
                "planned_prompt_sha256": _sha256_text(prompt),
            }
        )
        if args.json:
            sys.stdout.write(json.dumps(dry_packet, ensure_ascii=True, sort_keys=True) + "\n")
        else:
            sys.stdout.write("WBP DIP dry run prepared.\n")
        return int(dry_packet["exit_code"])

    proof_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(profile_dir),
            "WBP_PROFILE_DIR": str(profile_dir),
            "WBP_MANAGED_DIR": str(profile_dir / "managed"),
            "WBP_CONFIG_TOML": str(profile_dir / "config.toml"),
        }
    )
    if codex_executable and task:
        with output_jsonl.open("w", encoding="utf-8") as stdout_handle:
            completed = subprocess.run(
                argv_to_run,
                cwd=str(repo_root),
                env=env,
                stdout=stdout_handle,
                stderr=subprocess.DEVNULL if args.json else None,
                text=True,
                check=False,
            )
        codex_exit_code = int(completed.returncode)
    existing_changed_files = [path for path in changed_files if Path(path).exists()]
    packet = build_wbp_dip_tool_packet(
        task=task,
        expected_alias=expected_alias,
        codex_exit_code=codex_exit_code,
        codex_exec_jsonl_file=output_jsonl,
        output_last_message_file=output_last_message,
        entry_evidence_file=entry_evidence_file,
        proof_dir=proof_dir,
        dry_run=False,
        codex_executable=codex_executable,
        changed_files=[*existing_changed_files, str(proof_dir / "wbp-dip-tool.packet.json")],
        secret_values=[task],
    )
    packet_file = proof_dir / "wbp-dip-tool.packet.json"
    _write_json(packet_file, packet)
    if args.json:
        sys.stdout.write(json.dumps(packet, ensure_ascii=True, sort_keys=True) + "\n")
    else:
        if output_last_message.is_file():
            last_message = output_last_message.read_text(encoding="utf-8")
            sys.stdout.write(last_message)
            if not last_message.endswith("\n"):
                sys.stdout.write("\n")
        else:
            sys.stdout.write(str(packet["human_message"]) + "\n")
    return int(packet["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
