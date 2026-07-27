# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import time
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .codex_working_flow_delivery_proof import (
    WBP_DIP_HOOK_ORIGIN_LIVE_PROVIDER_DELIVERY_SOURCE_PACKET_KIND,
    _safe_working_flow_delivery_payload,
    _source_approved_handoff_payload,
    run_codex_working_flow_delivery_proof_command,
)
from .core import packets
from .custom_codex_auth_session_readiness import (
    CUSTOM_CODEX_AUTH_SESSION_API_KEY_ONLY,
    CUSTOM_CODEX_AUTH_SESSION_READINESS_PACKET_KIND,
    SESSION_STATE_API_KEY_ONLY,
    run_custom_codex_auth_session_readiness_command,
)
from .observed_machine_handoff_delivery import _canonical_json_digest
from .real_custom_codex_hook_proof import runtime_context_digest
from .real_user_prompt_submit_ledger_proof import (
    REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
    run_real_user_prompt_submit_ledger_proof_command,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths, write_json_atomic
from .user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    build_user_prompt_submit_readiness_packet,
    hook_ledger_path,
)
from .wbp_dip_hook_origin_proof import (
    WBP_DIP_HOOK_ORIGIN_OK,
    run_wbp_dip_hook_origin_proof_command,
)
from .wbp_dip_tool import (
    DEFAULT_CODEX_JSONL_FILENAME,
    DEFAULT_MODEL,
    DEFAULT_SANDBOX,
    _exact_plain_reply_requested,
    build_codex_exec_argv,
    default_codex_bin,
    _find_delegate_packet,
    _read_codex_exec_jsonl,
    _redact_text_file,
    _redaction_replacements,
)


REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND = "wbp_repeatable_real_custom_dip_proof_runner"
REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_PACKET_KIND = (
    "wbp_repeatable_real_custom_dip_proof_runner_manifest"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF = "proof"
REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK = "work"
REAL_CUSTOM_DIP_PROOF_RUNNER_MODES = frozenset(
    {
        REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
        REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    }
)

REAL_CUSTOM_DIP_PROOF_RUNNER_OK = "OK"
REAL_CUSTOM_DIP_PROOF_RUNNER_INPUT_INVALID = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_INPUT_INVALID"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_READINESS_FAILED = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_READINESS_FAILED"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_HOOK_LEDGER_NOT_FRESH = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_HOOK_LEDGER_NOT_FRESH"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_LEDGER_PROOF_FAILED = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_LEDGER_PROOF_FAILED"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED = "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED"
REAL_CUSTOM_DIP_PROOF_RUNNER_JOIN_FAILED = "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_JOIN_FAILED"
REAL_CUSTOM_DIP_PROOF_RUNNER_DELIVERY_FAILED = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_DELIVERY_FAILED"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_REPEATABILITY_FAILED = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_REPEATABILITY_FAILED"
)
REAL_CUSTOM_DIP_PROOF_RUNNER_UNSAFE_PACKET = "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_UNSAFE_PACKET"
REAL_CUSTOM_DIP_PROOF_RUNNER_ARTIFACT_WRITE_FAILED = (
    "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_ARTIFACT_WRITE_FAILED"
)

REAL_CUSTOM_DIP_PROOF_RUNNER_FILE_NAME = "real-custom-dip-proof-runner.packet.json"
REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_FILE_NAME = (
    "real-custom-dip-proof-runner-manifest.json"
)
HOOK_READINESS_FILE_NAME = "user-prompt-submit-readiness.packet.json"
CUSTOM_CODEX_AUTH_SESSION_READINESS_FILE_NAME = (
    "custom-codex-auth-session-readiness.packet.json"
)
LEDGER_PROOF_FILE_NAME = "real-user-prompt-submit-ledger-proof.packet.json"
WBP_DIP_HOOK_ORIGIN_FILE_NAME = "wbp-dip-hook-origin-proof.packet.json"
WORKING_FLOW_SOURCE_FILE_NAME = "working-flow-source-proof.packet.json"
WORKING_FLOW_CODEX_JSONL_FILE_NAME = "working-flow-codex-exec.jsonl"
WORKING_FLOW_LAST_MESSAGE_FILE_NAME = "working-flow-last-message.txt"
WORKING_FLOW_ENTRY_EVIDENCE_FILE_NAME = "working-flow-mcp-entry-evidence.json"
WORKING_FLOW_DELIVERY_FILE_NAME = "codex-working-flow-delivery-proof.packet.json"

_RUN_REQUIRED_TRUE_FIELDS = (
    "custom_codex_flow_proven",
    "user_prompt_submit_hook_ran",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "delegate_to_dip_proven",
    "api_lane_called",
    "route_bound_dispatch_proven",
    "live_result_available",
    "api_route_live_response_proven",
    "positive_api_route_response_gate_satisfied",
)
_RUN_DELIVERY_REQUIRED_TRUE_FIELDS = (
    "codex_working_flow_delivery_proven",
    "approved_delivery_surface_proven",
    "assistant_response_bound_to_handoff_digest",
)
_RUN_STRICT_REQUIRED_TRUE_FIELDS = (
    *_RUN_REQUIRED_TRUE_FIELDS,
    *_RUN_DELIVERY_REQUIRED_TRUE_FIELDS,
)
_JOIN_REQUIRED_TRUE_FIELDS = tuple(
    field
    for field in _RUN_STRICT_REQUIRED_TRUE_FIELDS
    if field
    not in {
        "codex_working_flow_delivery_proven",
        "approved_delivery_surface_proven",
        "assistant_response_bound_to_handoff_digest",
    }
)
_RUN_REQUIRED_FALSE_FIELDS = (
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "custom_codex_ui_visibility_proven",
    "product_ready",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_session_id() -> str:
    seed = f"{_utc_stamp()}:{os.getpid()}:{time.monotonic_ns()}"
    return _sha256_text(seed)[:16]


def _sha256_file(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _normalize_run_mode(value: object) -> str:
    mode = _safe_text(value, limit=32).casefold()
    return mode if mode in REAL_CUSTOM_DIP_PROOF_RUNNER_MODES else ""


def _required_runs_for_mode(mode: str) -> int:
    if mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK:
        return 1
    return 2


def _api_backed_custom_codex_gate_failures(
    packet: Mapping[str, Any],
    *,
    required: bool,
) -> list[str]:
    if not required:
        return []
    failures: list[str] = []
    if not packet:
        return ["api_backed_auth_session_packet_missing"]
    if packet.get("packet_kind") != CUSTOM_CODEX_AUTH_SESSION_READINESS_PACKET_KIND:
        failures.append("api_backed_auth_session_packet_kind_invalid")
    if packet.get("machine_error_code") != CUSTOM_CODEX_AUTH_SESSION_API_KEY_ONLY:
        failures.append("api_backed_auth_session_not_api_key_only")
    if packet.get("session_state") != SESSION_STATE_API_KEY_ONLY:
        failures.append("api_backed_auth_session_state_not_api_key_only")
    if packet.get("api_key_only") is not True:
        failures.append("api_backed_auth_session_api_key_only_not_proven")
    if packet.get("api_key_only_counts_as_ui_session") is not False:
        failures.append("api_key_only_counts_as_ui_session")
    if packet.get("logged_in_ui_session_proven") is not False:
        failures.append("logged_in_ui_session_proven")
    if packet.get("user_prompt_submit_hook_ready") is not True:
        failures.append("api_backed_auth_session_hook_not_ready")
    if packet.get("expected_custom_user_data_dir_observed") is not True:
        failures.append("api_backed_custom_user_data_dir_not_observed")
    if packet.get("app_server_account_bound_to_expected_user_data") is not True:
        failures.append("api_backed_app_server_account_not_bound_to_user_data")
    if packet.get("product_ready") is not False:
        failures.append("api_backed_auth_session_product_ready_claimed")
    if packet.get("fallback_used") is not False:
        failures.append("api_backed_auth_session_fallback_used")
    if packet.get("local_imitation_used") is not False:
        failures.append("api_backed_auth_session_local_imitation_used")
    if packet.get("native_codex_subagent_used_as_dip") is not False:
        failures.append("api_backed_auth_session_native_subagent_used")
    return sorted(set(failures))


def _proof_scope_for_mode(mode: str) -> str:
    if mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK:
        return (
            "single_run_real_custom_codex_hook_origin_to_wbp_dip_live_dispatch_"
            "and_working_flow_delivery_operator_work"
        )
    return (
        "repeatable_real_custom_codex_hook_origin_to_wbp_dip_live_dispatch_"
        "and_working_flow_delivery"
    )


def _proof_root(paths: RuntimePaths, proof_dir: str | None) -> Path:
    if proof_dir:
        return Path(proof_dir).expanduser()
    return paths.managed_dir / "codex-runner" / "real-custom-dip-proof" / _utc_stamp()


def _repo_root_from_cwd(codex_cwd: str | None) -> Path:
    if codex_cwd:
        return Path(codex_cwd).expanduser().resolve()
    return Path.cwd().resolve()


def _runtime_secret_values(runtime_context: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(runtime_context, Mapping):
        return []
    values: list[str] = []
    for route_id in runtime_context.get("allowed_api_route_ids", []):
        if isinstance(route_id, str) and route_id:
            values.append(route_id)
    for slot in runtime_context.get("slots", []):
        if isinstance(slot, Mapping):
            for key in ("route_id",):
                value = slot.get(key)
                if isinstance(value, str) and value:
                    values.append(value)
    return sorted(set(values))


def _ledger_file_metadata(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {
            "hook_ledger_file_present": False,
            "hook_ledger_file_sha256": "",
            "hook_ledger_file_mtime_ns": 0,
            "hook_ledger_file_path_recorded": False,
        }
    return {
        "hook_ledger_file_present": path.is_file(),
        "hook_ledger_file_sha256": _sha256_file(path),
        "hook_ledger_file_mtime_ns": int(stat.st_mtime_ns),
        "hook_ledger_file_path_recorded": False,
    }


def _ledger_fresh(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    if after.get("hook_ledger_file_present") is not True:
        return False
    before_sha = _hex_sha256(before.get("hook_ledger_file_sha256"))
    after_sha = _hex_sha256(after.get("hook_ledger_file_sha256"))
    before_mtime = int(before.get("hook_ledger_file_mtime_ns") or 0)
    after_mtime = int(after.get("hook_ledger_file_mtime_ns") or 0)
    if not before_sha:
        return bool(after_sha)
    return bool(after_sha and after_sha != before_sha and after_mtime >= before_mtime)


def _ledger_matches_prompt_digest(path: Path, expected_prompt_digest: str) -> bool:
    expected = _hex_sha256(expected_prompt_digest)
    if not expected:
        return False
    packet = _read_json_mapping(path)
    return packet.get("prompt_digest") == expected


def _write_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, dict(payload))


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _packet_file_summary(name: str, path: Path, packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_name": name,
        "packet_kind": _safe_text(packet.get("packet_kind"), limit=96),
        "status": _safe_text(packet.get("status"), limit=32),
        "machine_error_code": _safe_text(packet.get("machine_error_code"), limit=128),
        "file_present": path.is_file(),
        "file_sha256": _sha256_file(path),
        "file_path_recorded": False,
    }


def _completed_process_metadata(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    terminal_sha = _hex_sha256(getattr(completed, "wbp_terminal_output_sha256", ""))
    terminal_bytes = int(getattr(completed, "wbp_terminal_output_bytes", 0) or 0)
    return {
        "process_returncode": int(completed.returncode),
        "process_stdout_sha256": _sha256_text(completed.stdout or ""),
        "process_stderr_sha256": _sha256_text(completed.stderr or ""),
        "terminal_output_sha256": terminal_sha,
        "terminal_output_bytes": terminal_bytes,
        "terminal_output_recorded": False,
        "elapsed_ms": int(getattr(completed, "wbp_elapsed_ms", 0) or 0),
        "prompt_submit_key_sent": bool(
            getattr(completed, "wbp_prompt_submit_key_sent", False)
        ),
        "process_stdout_recorded": False,
        "process_stderr_recorded": False,
        "command_argv_recorded": False,
    }


def _run_custom_codex_prompt(
    *,
    codex_bin: Path,
    repo_root: Path,
    model: str,
    sandbox: str,
    prompt_text: str,
    profile_dir: Path,
    timeout_seconds: int,
    ledger_path: Path,
    expected_ledger_digest: str,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(profile_dir),
            "WBP_PROFILE_DIR": str(profile_dir),
            "WBP_MANAGED_DIR": str(profile_dir / "managed"),
            "WBP_EXTERNAL_MODELS_DIR": str(profile_dir / "managed" / "external-models"),
            "WBP_CONFIG_TOML": str(profile_dir / "config.toml"),
            "TERM": env.get("TERM") if env.get("TERM") not in {"", "dumb"} else "xterm-256color",
        }
    )
    argv = [
            str(codex_bin),
            "--no-alt-screen",
            "--enable",
            "hooks",
            "--dangerously-bypass-hook-trust",
            "--cd",
            str(repo_root),
            "--sandbox",
            sandbox,
            "-m",
            model,
            prompt_text,
    ]
    started = time.monotonic()
    master_fd = -1
    slave_fd = -1
    proc: subprocess.Popen[bytes] | None = None
    output_hasher = hashlib.sha256()
    output_bytes = 0
    returncode = 1
    submit_key_sent = False
    try:
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(repo_root),
            env=env,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = -1
        deadline = started + max(5, int(timeout_seconds))
        while time.monotonic() < deadline:
            try:
                ready, _, _ = select.select([master_fd], [], [], 0.2)
            except OSError:
                ready = []
            if ready:
                try:
                    chunk = os.read(master_fd, 8192)
                except OSError:
                    chunk = b""
                if chunk:
                    output_hasher.update(chunk)
                    output_bytes += len(chunk)
            if _ledger_matches_prompt_digest(ledger_path, expected_ledger_digest):
                returncode = 0
                break
            if (
                not submit_key_sent
                and time.monotonic() - started >= 1.0
                and master_fd >= 0
            ):
                try:
                    os.write(master_fd, b"\r")
                    submit_key_sent = True
                except OSError:
                    submit_key_sent = False
            if proc.poll() is not None:
                returncode = int(proc.returncode or 0)
                break
        else:
            returncode = 124
    finally:
        if slave_fd >= 0:
            try:
                os.close(slave_fd)
            except OSError:
                pass
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if master_fd >= 0:
            try:
                os.close(master_fd)
            except OSError:
                pass
    elapsed_ms = int((time.monotonic() - started) * 1000)
    completed = subprocess.CompletedProcess(
        args=argv,
        returncode=returncode,
        stdout="",
        stderr="",
    )
    completed.wbp_terminal_output_sha256 = output_hasher.hexdigest()  # type: ignore[attr-defined]
    completed.wbp_terminal_output_bytes = output_bytes  # type: ignore[attr-defined]
    completed.wbp_elapsed_ms = elapsed_ms  # type: ignore[attr-defined]
    completed.wbp_prompt_submit_key_sent = submit_key_sent  # type: ignore[attr-defined]
    return completed


def _run_wbp_dip_tool(
    *,
    repo_root: Path,
    profile_dir: Path,
    codex_bin: Path,
    model: str,
    sandbox: str,
    proof_dir: Path,
    expected_alias: str,
    task: str,
    timeout_seconds: int,
    dip_work_mode: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    proof_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(profile_dir),
            "WBP_PROFILE_DIR": str(profile_dir),
            "WBP_MANAGED_DIR": str(profile_dir / "managed"),
            "WBP_EXTERNAL_MODELS_DIR": str(profile_dir / "managed" / "external-models"),
            "WBP_CONFIG_TOML": str(profile_dir / "config.toml"),
        }
    )
    completed = subprocess.run(
        [
            str(repo_root / "tools" / "wbp_dip"),
            "--json",
            "--alias",
            expected_alias,
            "--profile-dir",
            str(profile_dir),
            "--codex-bin",
            str(codex_bin),
            "--model",
            model,
            "--sandbox",
            sandbox,
            "--work-mode",
            dip_work_mode,
            "--cd",
            str(repo_root),
            "--proof-dir",
            str(proof_dir),
            task,
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    packet_file = proof_dir / "wbp-dip-tool.packet.json"
    packet = _read_json_mapping(packet_file)
    if not packet and completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, Mapping):
            packet = dict(parsed)
            _write_artifact(packet_file, packet)
    return completed, packet, packet_file


def _build_delivery_delegate_prompt(*, task: str, expected_alias: str) -> str:
    payload = {
        "task": task,
        "expected_alias": expected_alias,
    }
    return (
        "Use only the WBP MCP tool. Do not run shell commands. Do not inspect "
        "files. Call delegate_to_dip exactly once with the JSON arguments below. "
        "The WBP MCP server is configured with a file-backed working-flow source "
        "proof. After the tool returns, answer exactly one line in this form: "
        "wbp_handoff_digest=<handoff_payload_sha256>. Do not answer locally, do "
        "not create a Codex sub-agent as DIP, and do not include route ids, "
        "secrets, backend details, or the task text.\n\n"
        f"delegate_to_dip arguments JSON: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def _delivery_source_failures(
    *,
    delegate_packet: Mapping[str, Any],
    dip_packet: Mapping[str, Any],
    join_packet: Mapping[str, Any],
    prompt_digest: str,
) -> list[str]:
    failures: list[str] = []
    if not delegate_packet:
        failures.append("delegate_packet_missing")
    if join_packet.get("status") != "ok":
        failures.append("join_packet_not_ok")
    if join_packet.get("prompt_digest") != prompt_digest:
        failures.append("join_prompt_digest_mismatch")
    if delegate_packet.get("task_sha256") != prompt_digest:
        failures.append("delegate_prompt_digest_mismatch")
    for field, source, reason in (
        ("custom_codex_flow_proven", join_packet, "custom_codex_flow_not_proven"),
        ("user_prompt_submit_hook_ran", join_packet, "user_prompt_submit_hook_not_run"),
        ("hook_prompt_digest_bound", join_packet, "hook_prompt_digest_not_bound"),
        (
            "hook_runtime_context_digest_bound",
            join_packet,
            "hook_runtime_context_not_bound",
        ),
        ("delegate_to_dip_proven", join_packet, "delegate_to_dip_not_proven"),
        ("api_lane_called", join_packet, "api_lane_not_called"),
        ("route_bound_dispatch_proven", join_packet, "route_bound_dispatch_not_proven"),
        ("live_result_available", join_packet, "live_result_not_available"),
        (
            "delegate_to_dip_tool_called",
            delegate_packet,
            "delegate_tool_call_not_observed",
        ),
        ("alias_context_read", delegate_packet, "alias_context_not_read"),
        (
            "allowed_api_route_ids_enforced",
            delegate_packet,
            "allowed_api_route_ids_not_enforced",
        ),
        ("route_allowed", delegate_packet, "route_id_not_allowed"),
        (
            "route_bound_dispatch_proven",
            delegate_packet,
            "dispatch_not_proven",
        ),
    ):
        if source.get(field) is not True:
            failures.append(reason)
    for field, source, reason in (
        ("fallback_used", join_packet, "fallback_used"),
        ("local_imitation_used", join_packet, "local_imitation_used"),
        (
            "native_codex_subagent_used_as_dip",
            join_packet,
            "native_codex_subagent_used_as_dip",
        ),
    ):
        if source.get(field) is not False:
            failures.append(reason)
    if not (
        _positive_api_route_response_gate_satisfied(join_packet)
        or _positive_api_route_response_gate_satisfied(dip_packet)
    ):
        failures.append("positive_api_route_response_gate_not_satisfied")
    for field, source, reason in (
        ("selected_api_route_id_sha256", delegate_packet, "selected_route_digest_missing"),
        ("route_bound_request_sha256", delegate_packet, "route_request_digest_missing"),
        (
            "controlled_provider_response_sha256",
            delegate_packet,
            "controlled_provider_response_digest_missing",
        ),
        ("live_result_text_sha256", dip_packet, "live_provider_response_digest_missing"),
    ):
        if not _hex_sha256(source.get(field)):
            failures.append(reason)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _direct_provider_response_gate_satisfied(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("direct_provider_auth_proven") is True
        and packet.get("direct_provider_response_observed") is True
        and packet.get("provider_auth_ok") is True
        and packet.get("positive_provider_proof_gate_satisfied") is True
        and packet.get("live_result_bridge_or_file_bridge_used") is not True
    )


def _server_owned_bridge_response_gate_satisfied(packet: Mapping[str, Any]) -> bool:
    bridge_used = packet.get("live_result_bridge_or_file_bridge_used") is True
    server_owned_bridge = (
        packet.get("live_result_runtime_context_bridge_used") is True
        or packet.get("live_result_runtime_context_file_bridge_used") is True
        or packet.get("server_owned_bridge_or_file_bridge_response_proven") is True
    )
    return bool(
        bridge_used
        and server_owned_bridge
        and packet.get("live_result_available") is True
        and (
            packet.get("live_result_provider_called") is True
            or packet.get("api_lane_called") is True
        )
        and (
            packet.get("live_result_route_allowed") is True
            or packet.get("route_bound_dispatch_proven") is True
        )
        and packet.get("route_bound_dispatch_proven") is True
        and packet.get("fallback_used") is not True
        and packet.get("local_imitation_used") is not True
        and packet.get("live_result_machine_error_code") in {None, "OK"}
        and bool(_hex_sha256(packet.get("live_result_text_sha256")))
        and packet.get("live_result_raw_backend_details_exposed") is not True
        and packet.get("live_result_secret_value_exposed") is not True
    )


def _positive_api_route_response_gate_satisfied(packet: Mapping[str, Any]) -> bool:
    packet_level_gate = bool(
        packet.get("api_route_live_response_proven") is True
        and packet.get("positive_api_route_response_gate_satisfied") is True
        and packet.get("delegate_to_dip_proven") is True
        and packet.get("api_lane_called") is True
        and packet.get("route_bound_dispatch_proven") is True
        and packet.get("live_result_available") is True
        and (
            packet.get("live_result_digest_bound") is True
            or bool(_hex_sha256(packet.get("live_result_text_sha256")))
        )
        and packet.get("fallback_used") is not True
        and packet.get("local_imitation_used") is not True
    )
    return bool(
        packet_level_gate
        or _direct_provider_response_gate_satisfied(packet)
        or _server_owned_bridge_response_gate_satisfied(packet)
    )


def _build_working_flow_source_packet(
    *,
    prompt_text: str,
    expected_alias: str,
    delegate_packet: Mapping[str, Any],
    dip_packet: Mapping[str, Any],
    ledger_packet: Mapping[str, Any],
    join_packet: Mapping[str, Any],
    ledger_file: Path,
    dip_file: Path,
    join_file: Path,
    secret_values: Sequence[str],
) -> dict[str, Any]:
    prompt_digest = _sha256_text(prompt_text)
    selected_route_digest = _hex_sha256(delegate_packet.get("selected_api_route_id_sha256"))
    route_bound_request_digest = _hex_sha256(delegate_packet.get("route_bound_request_sha256"))
    controlled_digest = _hex_sha256(delegate_packet.get("controlled_provider_response_sha256"))
    live_provider_digest = _hex_sha256(dip_packet.get("live_result_text_sha256"))
    failures = _delivery_source_failures(
        delegate_packet=delegate_packet,
        dip_packet=dip_packet,
        join_packet=join_packet,
        prompt_digest=prompt_digest,
    )
    ok = not failures
    server_owned_bridge_response_proven = (
        _server_owned_bridge_response_gate_satisfied(join_packet)
        or _server_owned_bridge_response_gate_satisfied(dip_packet)
    )
    positive_api_route_response_gate = (
        _positive_api_route_response_gate_satisfied(join_packet)
        or _positive_api_route_response_gate_satisfied(dip_packet)
    )
    source_extra: dict[str, Any] = {
        "schema_version": 1,
        "packet_kind": WBP_DIP_HOOK_ORIGIN_LIVE_PROVIDER_DELIVERY_SOURCE_PACKET_KIND,
        "source_packet_version": 1,
        "proof_scope": "custom_codex_hook_origin_wbp_dip_api_route_response_delivery_source",
        "dispatch_packet_kind": _safe_text(delegate_packet.get("packet_kind"), limit=96),
        "source_dispatch_packet_kind": _safe_text(
            delegate_packet.get("packet_kind"),
            limit=96,
        ),
        "prompt_digest": prompt_digest,
        "same_prompt_digest": bool(
            ok
            and join_packet.get("prompt_digest") == prompt_digest
            and delegate_packet.get("task_sha256") == prompt_digest
            and dip_packet.get("task_sha256") == prompt_digest
        ),
        "selected_alias": _safe_text(
            delegate_packet.get("selected_alias") or expected_alias,
            limit=80,
        ),
        "selected_alias_lane": _safe_text(
            delegate_packet.get("selected_alias_lane"),
            limit=32,
        ),
        "selected_slot": _safe_text(
            join_packet.get("selected_slot") or dip_packet.get("selected_slot"),
            limit=64,
        ),
        "selected_api_route_id_sha256": selected_route_digest,
        "route_bound_request_sha256": route_bound_request_digest,
        "controlled_provider_response_digest": controlled_digest,
        "provider_response_digest": controlled_digest,
        "live_provider_response_digest": live_provider_digest,
        "dispatch_truth_source": _safe_text(
            delegate_packet.get("dispatch_truth_source"),
            limit=80,
        ),
        "api_lane_truth_source": "server_owned_controlled_route_bound_dispatch",
        "live_provider_truth_source": "server_owned_external_live_provider_response",
        "custom_codex_flow_proven": join_packet.get("custom_codex_flow_proven") is True,
        "user_prompt_submit_hook_ran": join_packet.get("user_prompt_submit_hook_ran") is True,
        "hook_ledger_written": ledger_packet.get("hook_ledger_written") is True,
        "hook_prompt_digest_bound": join_packet.get("hook_prompt_digest_bound") is True,
        "hook_runtime_context_digest_bound": (
            join_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "thread_or_turn_digest_bound": ledger_packet.get("thread_or_turn_digest_bound") is True,
        "alias_context_read": delegate_packet.get("alias_context_read") is True,
        "alias_bound": True,
        "alias_resolved": True,
        "route_id_allowed": delegate_packet.get("route_allowed") is True,
        "allowed_api_route_ids_enforced": (
            delegate_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "selected_api_route_id_present": bool(selected_route_digest),
        "real_ledger_bound_api_dispatch_proven": (
            join_packet.get("real_ledger_bound_api_dispatch_proven") is True
            or join_packet.get("delegate_to_dip_proven") is True
        ),
        "delegate_to_dip_proven": join_packet.get("delegate_to_dip_proven") is True,
        "api_lane_called": join_packet.get("api_lane_called") is True,
        "dispatch_status": (
            "proven" if delegate_packet.get("route_bound_dispatch_proven") is True else ""
        ),
        "dispatch_proven": delegate_packet.get("route_bound_dispatch_proven") is True,
        "route_bound_dispatch_proven": (
            join_packet.get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": join_packet.get("live_result_available") is True,
        "direct_provider_auth_proven": (
            join_packet.get("direct_provider_auth_proven") is True
        ),
        "direct_provider_response_observed": (
            join_packet.get("direct_provider_response_observed") is True
        ),
        "provider_auth_ok": join_packet.get("provider_auth_ok") is True,
        "positive_provider_proof_gate_satisfied": (
            join_packet.get("positive_provider_proof_gate_satisfied") is True
        ),
        "server_owned_bridge_or_file_bridge_response_proven": (
            server_owned_bridge_response_proven
        ),
        "api_route_live_response_proven": positive_api_route_response_gate,
        "positive_api_route_response_gate_satisfied": positive_api_route_response_gate,
        "live_provider_status": "proven" if live_provider_digest else "",
        "live_provider_proven": bool(live_provider_digest),
        "live_provider_response_proven": bool(live_provider_digest),
        "external_live_provider_response_proven": bool(live_provider_digest),
        "fallback_used": join_packet.get("fallback_used") is True,
        "local_imitation_used": join_packet.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            join_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "live_result_bridge_or_file_bridge_used": (
            join_packet.get("live_result_bridge_or_file_bridge_used") is True
            or dip_packet.get("live_result_bridge_or_file_bridge_used") is True
        ),
        "hook_ledger_failures": [],
        "dispatch_failures": [],
        "wbp_dip_failures": [],
        "join_failures": [],
        "delivery_source_failures": [] if ok else failures,
        "blocking_reasons": [] if ok else failures,
        "ledger_proof_file_sha256": _sha256_file(ledger_file),
        "wbp_dip_file_sha256": _sha256_file(dip_file),
        "join_file_sha256": _sha256_file(join_file),
        "source_files_path_recorded": False,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "fallback_used_recorded_as_failure": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    source_extra["handoff_payload_digest"] = _canonical_json_digest(
        _source_approved_handoff_payload(source_extra)
    )
    source_extra["working_flow_handoff_payload_digest"] = _hex_sha256(
        _safe_working_flow_delivery_payload(source_extra).get("handoff_payload_sha256")
    )
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP prepared file-backed DIP delivery source proof."
            if ok
            else "WBP blocked DIP delivery source proof before Codex handoff."
        ),
        machine_error_code="OK" if ok else "WBP_DIP_DELIVERY_SOURCE_INVALID",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values),
        extra=source_extra,
    )


def _run_working_flow_delivery(
    *,
    run_dir: Path,
    repo_root: Path,
    profile_dir: Path,
    codex_bin: Path,
    model: str,
    sandbox: str,
    expected_alias: str,
    prompt_text: str,
    timeout_seconds: int,
    ledger_packet: Mapping[str, Any],
    dip_packet: Mapping[str, Any],
    join_packet: Mapping[str, Any],
    ledger_file: Path,
    dip_file: Path,
    join_file: Path,
) -> dict[str, Any]:
    source_file = run_dir / WORKING_FLOW_SOURCE_FILE_NAME
    delivery_jsonl_file = run_dir / WORKING_FLOW_CODEX_JSONL_FILE_NAME
    delivery_last_message_file = run_dir / WORKING_FLOW_LAST_MESSAGE_FILE_NAME
    entry_evidence_file = run_dir / WORKING_FLOW_ENTRY_EVIDENCE_FILE_NAME
    delivery_file = run_dir / WORKING_FLOW_DELIVERY_FILE_NAME
    delegate_packet = _find_delegate_packet(
        _read_codex_exec_jsonl(dip_file.parent / DEFAULT_CODEX_JSONL_FILENAME)
    )
    prompt = _build_delivery_delegate_prompt(task=prompt_text, expected_alias=expected_alias)
    secret_values = [prompt_text, prompt]
    source_packet = _build_working_flow_source_packet(
        prompt_text=prompt_text,
        expected_alias=expected_alias,
        delegate_packet=delegate_packet,
        dip_packet=dip_packet,
        ledger_packet=ledger_packet,
        join_packet=join_packet,
        ledger_file=ledger_file,
        dip_file=dip_file,
        join_file=join_file,
        secret_values=secret_values,
    )
    _write_artifact(source_file, source_packet)
    if source_packet.get("status") != "ok":
        return {
            "working_flow_source_packet": source_packet,
            "working_flow_delivery_packet": {},
            "working_flow_delivery_process": {},
            "artifacts": [
                _packet_file_summary(WORKING_FLOW_SOURCE_FILE_NAME, source_file, source_packet),
            ],
            "run_blocking_reasons": list(source_packet.get("blocking_reasons") or []),
        }
    argv = build_codex_exec_argv(
        codex_bin=codex_bin,
        repo_root=repo_root,
        model=model,
        sandbox=sandbox,
        prompt=prompt,
        output_jsonl=delivery_jsonl_file,
        output_last_message=delivery_last_message_file,
        profile_dir=profile_dir,
        entry_evidence_file=entry_evidence_file,
        extra_mcp_env={
            "WBP_MCP_WORKING_FLOW_SOURCE_PROOF_FILE": str(source_file),
        },
    )
    env = dict(os.environ)
    env.update(
        {
            "CODEX_HOME": str(profile_dir),
            "WBP_PROFILE_DIR": str(profile_dir),
            "WBP_MANAGED_DIR": str(profile_dir / "managed"),
            "WBP_CONFIG_TOML": str(profile_dir / "config.toml"),
        }
    )
    try:
        with delivery_jsonl_file.open("w", encoding="utf-8") as stdout_handle:
            completed = subprocess.run(
                argv,
                cwd=str(repo_root),
                env=env,
                stdout=stdout_handle,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
    except subprocess.TimeoutExpired:
        completed = subprocess.CompletedProcess(
            args=argv,
            returncode=124,
            stdout="",
            stderr="",
        )
    redactions = _redaction_replacements(task=prompt_text, prompt=prompt)
    _redact_text_file(delivery_jsonl_file, redactions)
    _redact_text_file(delivery_last_message_file, redactions)
    delivery_packet = run_codex_working_flow_delivery_proof_command(
        integrated_live_provider_proof_file=str(source_file),
        codex_exec_jsonl_file=str(delivery_jsonl_file),
    )
    _write_artifact(delivery_file, delivery_packet)
    delivery_failures = _delivery_failures(delivery_packet, completed)
    return {
        "working_flow_source_packet": source_packet,
        "working_flow_delivery_packet": delivery_packet,
        "working_flow_delivery_process": _completed_process_metadata(completed),
        "artifacts": [
            _packet_file_summary(WORKING_FLOW_SOURCE_FILE_NAME, source_file, source_packet),
            _packet_file_summary(WORKING_FLOW_DELIVERY_FILE_NAME, delivery_file, delivery_packet),
        ],
        "run_blocking_reasons": delivery_failures,
    }


def _delivery_failures(
    packet: Mapping[str, Any],
    completed: subprocess.CompletedProcess[str],
) -> list[str]:
    failures: list[str] = []
    if completed.returncode != 0:
        failures.append("working_flow_codex_exec_failed")
    if packet.get("status") != "ok":
        failures.append("working_flow_delivery_status_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("working_flow_delivery_machine_error_not_ok")
    for field in (
        "codex_working_flow_delivery_proven",
        "approved_delivery_surface_proven",
        "assistant_response_bound_to_handoff_digest",
    ):
        if packet.get(field) is not True:
            failures.append(f"{field}_not_true")
    for field in (
        "custom_codex_ui_visibility_proven",
        "delivery_counts_as_custom_codex_ui",
        "product_ready",
        "fallback_used",
        "local_imitation_used",
        "native_codex_subagent_used_as_dip",
    ):
        if packet.get(field) is not False:
            failures.append(f"{field}_not_false")
    blocking = packet.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        failures.extend(_safe_text(item, limit=96) for item in blocking)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _effective_prompt(base_prompt: str, run_index: int, run_session_id: str) -> str:
    marker = (
        f"WBP_REAL_CUSTOM_DIP_PROOF_RUN_{run_index:02d}_"
        f"{_sha256_text(base_prompt)[:12]}_{run_session_id}"
    )
    proof_suffix = (
        f"Proof run marker: {marker}. "
        "Answer shortly; do not expose route ids, secrets, or backend details."
    )
    if _exact_plain_reply_requested(base_prompt):
        return f"{proof_suffix} {base_prompt}"
    return f"{base_prompt} {proof_suffix}"


def _readiness_failures(readiness: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if readiness.get("status") != "ok":
        failures.append("hook_readiness_not_ok")
    if readiness.get("machine_error_code") != HOOK_CONFIG_OK:
        failures.append("hook_readiness_machine_error_not_ok")
    if readiness.get("hook_enabled") is not True:
        failures.append("hook_not_enabled")
    if readiness.get("hook_trusted") is not True:
        failures.append("hook_not_trusted")
    if readiness.get("hook_config_digest_bound") is not True:
        failures.append("hook_config_digest_not_bound")
    blocking = readiness.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        failures.extend(_safe_text(item, limit=96) for item in blocking)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _join_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("status") != "ok":
        failures.append("join_status_not_ok")
    if packet.get("machine_error_code") != WBP_DIP_HOOK_ORIGIN_OK:
        failures.append("join_machine_error_not_ok")
    for field in _JOIN_REQUIRED_TRUE_FIELDS:
        if packet.get(field) is not True:
            failures.append(f"{field}_not_true")
    for field in _RUN_REQUIRED_FALSE_FIELDS:
        if packet.get(field) is not False:
            failures.append(f"{field}_not_false")
    blocking = packet.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        failures.extend(_safe_text(item, limit=96) for item in blocking)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _ledger_proof_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("status") != "ok":
        failures.append("ledger_proof_status_not_ok")
    if packet.get("machine_error_code") != REAL_USER_PROMPT_SUBMIT_LEDGER_OK:
        failures.append("ledger_proof_machine_error_not_ok")
    for field in (
        "custom_codex_flow_proven",
        "user_prompt_submit_hook_ran",
        "hook_prompt_digest_bound",
        "hook_runtime_context_digest_bound",
    ):
        if packet.get(field) is not True:
            failures.append(f"{field}_not_true")
    blocking = packet.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        failures.extend(_safe_text(item, limit=96) for item in blocking)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _dip_failures(packet: Mapping[str, Any], completed: subprocess.CompletedProcess[str]) -> list[str]:
    failures: list[str] = []
    if completed.returncode != 0:
        failures.append("wbp_dip_process_failed")
    if packet.get("status") != "ok":
        failures.append("wbp_dip_status_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("wbp_dip_machine_error_not_ok")
    for field in (
        "delegate_to_dip_proven",
        "api_lane_called",
        "route_bound_dispatch_proven",
        "live_result_available",
    ):
        if packet.get(field) is not True:
            failures.append(f"{field}_not_true")
    if not _positive_api_route_response_gate_satisfied(packet):
        failures.append("positive_api_route_response_gate_not_satisfied")
    blocking = packet.get("blocking_reasons")
    if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes)):
        failures.extend(_safe_text(item, limit=96) for item in blocking)
    return sorted(set(failure for failure in failures if packets.is_command_value_token(failure)))


def _run_once(
    *,
    paths: RuntimePaths,
    run_dir: Path,
    prompt_text: str,
    codex_bin: Path,
    repo_root: Path,
    model: str,
    sandbox: str,
    expected_alias: str,
    timeout_seconds: int,
    codex_hook_current_hash: str,
    probe_codex_app_server: bool,
    run_mode: str,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = hook_ledger_path(paths)
    before = _ledger_file_metadata(ledger_path)
    codex_completed = _run_custom_codex_prompt(
        codex_bin=codex_bin,
        repo_root=repo_root,
        model=model,
        sandbox=sandbox,
        prompt_text=prompt_text,
        profile_dir=paths.profile_dir,
        timeout_seconds=timeout_seconds,
        ledger_path=ledger_path,
        expected_ledger_digest=_sha256_text(prompt_text),
    )
    after = _ledger_file_metadata(ledger_path)
    ledger_fresh = _ledger_fresh(before, after)
    if codex_completed.returncode != 0 or not ledger_fresh:
        return {
            "prompt_digest": _sha256_text(prompt_text),
            "codex_exec": _completed_process_metadata(codex_completed),
            "hook_ledger_before": before,
            "hook_ledger_after": after,
            "hook_ledger_fresh": ledger_fresh,
            "ledger_proof_packet": {},
            "wbp_dip_packet": {},
            "join_packet": {},
            "artifacts": [],
            "run_blocking_reasons": sorted(
                set(
                    [
                        *([] if codex_completed.returncode == 0 else ["custom_codex_exec_failed"]),
                        *([] if ledger_fresh else ["hook_ledger_not_fresh"]),
                    ]
                )
            ),
        }

    ledger_packet = run_real_user_prompt_submit_ledger_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    ledger_file = run_dir / LEDGER_PROOF_FILE_NAME
    _write_artifact(ledger_file, ledger_packet)
    ledger_failures = _ledger_proof_failures(ledger_packet)
    if ledger_failures:
        return {
            "prompt_digest": _sha256_text(prompt_text),
            "codex_exec": _completed_process_metadata(codex_completed),
            "hook_ledger_before": before,
            "hook_ledger_after": after,
            "hook_ledger_fresh": ledger_fresh,
            "ledger_proof_packet": ledger_packet,
            "wbp_dip_packet": {},
            "join_packet": {},
            "artifacts": [_packet_file_summary(LEDGER_PROOF_FILE_NAME, ledger_file, ledger_packet)],
            "run_blocking_reasons": ledger_failures,
        }

    wbp_dip_dir = run_dir / "wbp-dip"
    dip_work_mode = "full" if run_mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK else "standard"
    dip_completed, dip_packet, dip_file = _run_wbp_dip_tool(
        repo_root=repo_root,
        profile_dir=paths.profile_dir,
        codex_bin=codex_bin,
        model=model,
        sandbox=sandbox,
        proof_dir=wbp_dip_dir,
        expected_alias=expected_alias,
        task=prompt_text,
        timeout_seconds=timeout_seconds,
        dip_work_mode=dip_work_mode,
    )
    dip_failures = _dip_failures(dip_packet, dip_completed)
    if dip_failures:
        return {
            "prompt_digest": _sha256_text(prompt_text),
            "codex_exec": _completed_process_metadata(codex_completed),
            "wbp_dip_process": _completed_process_metadata(dip_completed),
            "hook_ledger_before": before,
            "hook_ledger_after": after,
            "hook_ledger_fresh": ledger_fresh,
            "ledger_proof_packet": ledger_packet,
            "wbp_dip_packet": dip_packet,
            "join_packet": {},
            "artifacts": [
                _packet_file_summary(LEDGER_PROOF_FILE_NAME, ledger_file, ledger_packet),
                _packet_file_summary("wbp-dip/wbp-dip-tool.packet.json", dip_file, dip_packet),
            ],
            "run_blocking_reasons": dip_failures,
        }

    join_packet = run_wbp_dip_hook_origin_proof_command(
        prompt_text=prompt_text,
        ledger_proof_file=str(ledger_file),
        wbp_dip_proof_file=str(dip_file),
        expected_alias=expected_alias,
    )
    join_file = run_dir / WBP_DIP_HOOK_ORIGIN_FILE_NAME
    _write_artifact(join_file, join_packet)
    join_failures = _join_failures(join_packet)
    if join_failures:
        return {
            "prompt_digest": _sha256_text(prompt_text),
            "codex_exec": _completed_process_metadata(codex_completed),
            "wbp_dip_process": _completed_process_metadata(dip_completed),
            "hook_ledger_before": before,
            "hook_ledger_after": after,
            "hook_ledger_fresh": ledger_fresh,
            "ledger_proof_packet": ledger_packet,
            "wbp_dip_packet": dip_packet,
            "join_packet": join_packet,
            "working_flow_source_packet": {},
            "working_flow_delivery_packet": {},
            "artifacts": [
                _packet_file_summary(LEDGER_PROOF_FILE_NAME, ledger_file, ledger_packet),
                _packet_file_summary("wbp-dip/wbp-dip-tool.packet.json", dip_file, dip_packet),
                _packet_file_summary(WBP_DIP_HOOK_ORIGIN_FILE_NAME, join_file, join_packet),
            ],
            "run_blocking_reasons": join_failures,
        }

    delivery_result = _run_working_flow_delivery(
        run_dir=run_dir,
        repo_root=repo_root,
        profile_dir=paths.profile_dir,
        codex_bin=codex_bin,
        model=model,
        sandbox=sandbox,
        expected_alias=expected_alias,
        prompt_text=prompt_text,
        timeout_seconds=timeout_seconds,
        ledger_packet=ledger_packet,
        dip_packet=dip_packet,
        join_packet=join_packet,
        ledger_file=ledger_file,
        dip_file=dip_file,
        join_file=join_file,
    )
    delivery_artifacts = delivery_result.get("artifacts")
    delivery_blocking = delivery_result.get("run_blocking_reasons")
    return {
        "prompt_digest": _sha256_text(prompt_text),
        "codex_exec": _completed_process_metadata(codex_completed),
        "wbp_dip_process": _completed_process_metadata(dip_completed),
        "working_flow_delivery_process": delivery_result.get("working_flow_delivery_process", {}),
        "hook_ledger_before": before,
        "hook_ledger_after": after,
        "hook_ledger_fresh": ledger_fresh,
        "ledger_proof_packet": ledger_packet,
        "wbp_dip_packet": dip_packet,
        "join_packet": join_packet,
        "working_flow_source_packet": delivery_result.get("working_flow_source_packet", {}),
        "working_flow_delivery_packet": delivery_result.get("working_flow_delivery_packet", {}),
        "artifacts": [
            _packet_file_summary(LEDGER_PROOF_FILE_NAME, ledger_file, ledger_packet),
            _packet_file_summary("wbp-dip/wbp-dip-tool.packet.json", dip_file, dip_packet),
            _packet_file_summary(WBP_DIP_HOOK_ORIGIN_FILE_NAME, join_file, join_packet),
            *(
                list(delivery_artifacts)
                if isinstance(delivery_artifacts, Sequence)
                and not isinstance(delivery_artifacts, (str, bytes))
                else []
            ),
        ],
        "run_blocking_reasons": (
            list(delivery_blocking)
            if isinstance(delivery_blocking, Sequence)
            and not isinstance(delivery_blocking, (str, bytes))
            else []
        ),
    }


def _run_summary(run_index: int, run: Mapping[str, Any]) -> dict[str, Any]:
    join = run.get("join_packet")
    join_packet = join if isinstance(join, Mapping) else {}
    ledger = run.get("ledger_proof_packet")
    ledger_packet = ledger if isinstance(ledger, Mapping) else {}
    dip = run.get("wbp_dip_packet")
    dip_packet = dip if isinstance(dip, Mapping) else {}
    delivery = run.get("working_flow_delivery_packet")
    delivery_packet = delivery if isinstance(delivery, Mapping) else {}
    codex_exec = run.get("codex_exec")
    codex_exec_metadata = codex_exec if isinstance(codex_exec, Mapping) else {}
    blocking = run.get("run_blocking_reasons")
    custom_codex_flow_proven = (
        join_packet.get("custom_codex_flow_proven") is True
        or ledger_packet.get("custom_codex_flow_proven") is True
    )
    user_prompt_submit_hook_ran = (
        join_packet.get("user_prompt_submit_hook_ran") is True
        or ledger_packet.get("user_prompt_submit_hook_ran") is True
    )
    hook_prompt_digest_bound = (
        join_packet.get("hook_prompt_digest_bound") is True
        or ledger_packet.get("hook_prompt_digest_bound") is True
    )
    hook_runtime_context_digest_bound = (
        join_packet.get("hook_runtime_context_digest_bound") is True
        or ledger_packet.get("hook_runtime_context_digest_bound") is True
    )
    delegate_to_dip_proven = (
        join_packet.get("delegate_to_dip_proven") is True
        or dip_packet.get("delegate_to_dip_proven") is True
    )
    api_lane_called = (
        join_packet.get("api_lane_called") is True
        or dip_packet.get("api_lane_called") is True
    )
    route_bound_dispatch_proven = (
        join_packet.get("route_bound_dispatch_proven") is True
        or dip_packet.get("route_bound_dispatch_proven") is True
    )
    live_result_available = (
        join_packet.get("live_result_available") is True
        or dip_packet.get("live_result_available") is True
    )
    direct_provider_auth_proven = (
        join_packet.get("direct_provider_auth_proven") is True
        or dip_packet.get("direct_provider_auth_proven") is True
    )
    direct_provider_response_observed = (
        join_packet.get("direct_provider_response_observed") is True
        or dip_packet.get("direct_provider_response_observed") is True
    )
    provider_auth_ok = (
        join_packet.get("provider_auth_ok") is True
        or dip_packet.get("provider_auth_ok") is True
    )
    positive_provider_proof_gate_satisfied = (
        join_packet.get("positive_provider_proof_gate_satisfied") is True
        or dip_packet.get("positive_provider_proof_gate_satisfied") is True
    )
    server_owned_bridge_response_proven = (
        _server_owned_bridge_response_gate_satisfied(join_packet)
        or _server_owned_bridge_response_gate_satisfied(dip_packet)
    )
    positive_api_route_response_gate_satisfied = (
        _positive_api_route_response_gate_satisfied(join_packet)
        or _positive_api_route_response_gate_satisfied(dip_packet)
    )
    codex_working_flow_delivery_proven = (
        delivery_packet.get("codex_working_flow_delivery_proven") is True
    )
    approved_delivery_surface_proven = (
        delivery_packet.get("approved_delivery_surface_proven") is True
    )
    assistant_response_bound_to_handoff_digest = (
        delivery_packet.get("assistant_response_bound_to_handoff_digest") is True
    )
    live_result_bridge_or_file_bridge_used = (
        join_packet.get("live_result_bridge_or_file_bridge_used") is True
        or dip_packet.get("live_result_bridge_or_file_bridge_used") is True
    )
    wbp_dip_live_result_text_limit = int(
        dip_packet.get("live_result_text_limit")
        if isinstance(dip_packet.get("live_result_text_limit"), int)
        else 0
    )
    wbp_dip_live_result_output_token_limit = int(
        dip_packet.get("live_result_output_token_limit")
        if isinstance(dip_packet.get("live_result_output_token_limit"), int)
        else 0
    )
    wbp_dip_repo_bridge_max_steps = int(
        dip_packet.get("repo_bridge_max_steps")
        if isinstance(dip_packet.get("repo_bridge_max_steps"), int)
        else 0
    )
    return {
        "run_index": run_index,
        "prompt_digest": _hex_sha256(run.get("prompt_digest")),
        "custom_codex_exec_returncode": int(
            codex_exec_metadata.get("process_returncode")
            if isinstance(codex_exec_metadata.get("process_returncode"), int)
            else 0
        ),
        "custom_codex_exec_elapsed_ms": int(
            codex_exec_metadata.get("elapsed_ms")
            if isinstance(codex_exec_metadata.get("elapsed_ms"), int)
            else 0
        ),
        "custom_codex_terminal_output_sha256": _hex_sha256(
            codex_exec_metadata.get("terminal_output_sha256")
        ),
        "custom_codex_terminal_output_bytes": int(
            codex_exec_metadata.get("terminal_output_bytes")
            if isinstance(codex_exec_metadata.get("terminal_output_bytes"), int)
            else 0
        ),
        "custom_codex_prompt_submit_key_sent": bool(
            codex_exec_metadata.get("prompt_submit_key_sent") is True
        ),
        "custom_codex_terminal_output_recorded": False,
        "custom_codex_process_stdout_recorded": False,
        "custom_codex_process_stderr_recorded": False,
        "custom_codex_command_argv_recorded": False,
        "hook_ledger_fresh": run.get("hook_ledger_fresh") is True,
        "custom_codex_flow_proven": custom_codex_flow_proven,
        "user_prompt_submit_hook_ran": user_prompt_submit_hook_ran,
        "hook_prompt_digest_bound": hook_prompt_digest_bound,
        "hook_runtime_context_digest_bound": hook_runtime_context_digest_bound,
        "delegate_to_dip_proven": delegate_to_dip_proven,
        "api_lane_called": api_lane_called,
        "route_bound_dispatch_proven": route_bound_dispatch_proven,
        "live_result_available": live_result_available,
        "direct_provider_auth_proven": direct_provider_auth_proven,
        "direct_provider_response_observed": direct_provider_response_observed,
        "provider_auth_ok": provider_auth_ok,
        "positive_provider_proof_gate_satisfied": positive_provider_proof_gate_satisfied,
        "server_owned_bridge_or_file_bridge_response_proven": (
            server_owned_bridge_response_proven
        ),
        "api_route_live_response_proven": positive_api_route_response_gate_satisfied,
        "positive_api_route_response_gate_satisfied": (
            positive_api_route_response_gate_satisfied
        ),
        "codex_working_flow_delivery_proven": codex_working_flow_delivery_proven,
        "approved_delivery_surface_proven": approved_delivery_surface_proven,
        "assistant_response_bound_to_handoff_digest": (
            assistant_response_bound_to_handoff_digest
        ),
        "live_result_bridge_or_file_bridge_used": live_result_bridge_or_file_bridge_used,
        "wbp_dip_work_mode": _safe_text(dip_packet.get("dip_work_mode"), limit=40),
        "wbp_dip_full_work_mode": dip_packet.get("dip_full_work_mode") is True,
        "wbp_dip_live_result_text_limit": wbp_dip_live_result_text_limit,
        "wbp_dip_live_result_output_token_limit": wbp_dip_live_result_output_token_limit,
        "wbp_dip_repo_bridge_max_steps": wbp_dip_repo_bridge_max_steps,
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": False,
        "fallback_used": join_packet.get("fallback_used") is True,
        "local_imitation_used": join_packet.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            join_packet.get("native_codex_subagent_used_as_dip") is True
        ),
        "custom_codex_ui_visibility_proven": (
            join_packet.get("custom_codex_ui_visibility_proven") is True
        ),
        "product_ready": join_packet.get("product_ready") is True,
        "raw_prompt_recorded": join_packet.get("raw_prompt_recorded") is True,
        "prompt_text_recorded": join_packet.get("prompt_text_recorded") is True,
        "natural_phrase_recorded": join_packet.get("natural_phrase_recorded") is True,
        "raw_route_id_recorded": join_packet.get("raw_route_id_recorded") is True,
        "selected_api_route_id_recorded": (
            join_packet.get("selected_api_route_id_recorded") is True
        ),
        "provider_response_text_recorded": (
            join_packet.get("provider_response_text_recorded") is True
        ),
        "provider_response_preview_recorded": (
            join_packet.get("provider_response_preview_recorded") is True
        ),
        "raw_backend_details_exposed": (
            join_packet.get("raw_backend_details_exposed") is True
        ),
        "secret_value_exposed": join_packet.get("secret_value_exposed") is True,
        "ledger_proof_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in run.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and item.get("artifact_name") == LEDGER_PROOF_FILE_NAME
                ),
                "",
            )
        ),
        "wbp_dip_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in run.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and item.get("artifact_name") == "wbp-dip/wbp-dip-tool.packet.json"
                ),
                "",
            )
        ),
        "join_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in run.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and item.get("artifact_name") == WBP_DIP_HOOK_ORIGIN_FILE_NAME
                ),
                "",
            )
        ),
        "working_flow_source_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in run.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and item.get("artifact_name") == WORKING_FLOW_SOURCE_FILE_NAME
                ),
                "",
            )
        ),
        "working_flow_delivery_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in run.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and item.get("artifact_name") == WORKING_FLOW_DELIVERY_FILE_NAME
                ),
                "",
            )
        ),
        "ledger_machine_error_code": _safe_text(
            ledger_packet.get("machine_error_code"),
            limit=128,
        ),
        "wbp_dip_machine_error_code": _safe_text(
            dip_packet.get("machine_error_code"),
            limit=128,
        ),
        "live_result_machine_error_code": _safe_text(
            dip_packet.get("live_result_machine_error_code"),
            limit=128,
        ),
        "live_result_source": _safe_text(
            dip_packet.get("live_result_source"),
            limit=128,
        ),
        "join_machine_error_code": _safe_text(
            join_packet.get("machine_error_code"),
            limit=128,
        ),
        "working_flow_delivery_machine_error_code": _safe_text(
            delivery_packet.get("machine_error_code"),
            limit=128,
        ),
        "working_flow_delivery_surface_kind": _safe_text(
            delivery_packet.get("working_flow_delivery_surface_kind"),
            limit=128,
        ),
        "working_flow_handoff_payload_digest": _hex_sha256(
            delivery_packet.get("working_flow_handoff_payload_digest")
            or delivery_packet.get("handoff_payload_digest")
        ),
        "blocking_reasons": sorted(
            {
                _safe_text(item, limit=96)
                for item in blocking
                if packets.is_command_value_token(_safe_text(item, limit=96))
            }
        )
        if isinstance(blocking, Sequence) and not isinstance(blocking, (str, bytes))
        else [],
    }


def _repeatability_failures(
    run_summaries: Sequence[Mapping[str, Any]],
    *,
    required_runs: int,
    require_working_flow_delivery: bool = True,
) -> list[str]:
    failures: list[str] = []
    if len(run_summaries) != required_runs:
        failures.append("required_run_count_not_met")
    prompt_digests = [_hex_sha256(run.get("prompt_digest")) for run in run_summaries]
    if len(set(prompt_digests)) != len(prompt_digests):
        failures.append("prompt_digests_not_distinct")
    for index, run in enumerate(run_summaries, start=1):
        run_blocking = run.get("blocking_reasons")
        if (
            not require_working_flow_delivery
            and _safe_text(run.get("working_flow_delivery_machine_error_code"), limit=128)
        ):
            run_blocking = []
        if run_blocking:
            failures.extend(
                f"run_{index}_{reason}"
                for reason in run_blocking
                if packets.is_command_value_token(str(reason))
            )
        if run.get("hook_ledger_fresh") is not True:
            failures.append(f"run_{index}_hook_ledger_not_fresh")
        required_true_fields = (
            _RUN_STRICT_REQUIRED_TRUE_FIELDS
            if require_working_flow_delivery
            else _RUN_REQUIRED_TRUE_FIELDS
        )
        for field in required_true_fields:
            if run.get(field) is not True:
                failures.append(f"run_{index}_{field}_not_true")
        for field in _RUN_REQUIRED_FALSE_FIELDS:
            if run.get(field) is not False:
                failures.append(f"run_{index}_{field}_not_false")
        required_hash_fields = [
            "ledger_proof_file_sha256",
            "wbp_dip_file_sha256",
            "join_file_sha256",
        ]
        if require_working_flow_delivery:
            required_hash_fields.extend(
                [
                    "working_flow_source_file_sha256",
                    "working_flow_delivery_file_sha256",
                ]
            )
        for field in required_hash_fields:
            if not _hex_sha256(run.get(field)):
                failures.append(f"run_{index}_{field}_missing")
    return sorted(set(failures))


def _build_manifest(
    *,
    run_mode: str,
    readiness_packet: Mapping[str, Any],
    run_summaries: Sequence[Mapping[str, Any]],
    runner_status: str,
    runner_machine_error_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_PACKET_KIND,
        "proof_scope": _proof_scope_for_mode(run_mode),
        "operator_command_mode": run_mode,
        "work_mode_cannot_mint_admission_proof": (
            run_mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
        ),
        "readiness": {
            "packet_kind": _safe_text(readiness_packet.get("packet_kind"), limit=96),
            "status": _safe_text(readiness_packet.get("status"), limit=32),
            "machine_error_code": _safe_text(
                readiness_packet.get("machine_error_code"),
                limit=128,
            ),
            "hook_enabled": readiness_packet.get("hook_enabled") is True,
            "hook_trusted": readiness_packet.get("hook_trusted") is True,
            "hook_config_digest_bound": (
                readiness_packet.get("hook_config_digest_bound") is True
            ),
        },
        "run_count": len(run_summaries),
        "runs": [dict(run) for run in run_summaries],
        "runner_status": runner_status,
        "runner_machine_error_code": runner_machine_error_code,
        "input_file_paths_recorded": False,
        "artifact_file_paths_recorded": False,
        "proof_dir_path_recorded": False,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "roadmap_recorded": False,
        "future_plan_recorded": False,
        "next_contour_recorded": False,
    }


def _machine_error_code(
    *,
    input_failures: Sequence[str],
    readiness_failures: Sequence[str],
    freshness_failures: Sequence[str],
    ledger_failures: Sequence[str],
    dip_failures: Sequence[str],
    join_failures: Sequence[str],
    delivery_failures: Sequence[str],
    repeatability_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    artifact_failures: Sequence[str],
) -> str:
    if artifact_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_ARTIFACT_WRITE_FAILED
    if unsafe_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_UNSAFE_PACKET
    if input_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_INPUT_INVALID
    if readiness_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_READINESS_FAILED
    if freshness_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_HOOK_LEDGER_NOT_FRESH
    if ledger_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_LEDGER_PROOF_FAILED
    if dip_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED
    if join_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_JOIN_FAILED
    if delivery_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_DELIVERY_FAILED
    if repeatability_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_REPEATABILITY_FAILED
    return REAL_CUSTOM_DIP_PROOF_RUNNER_OK


def build_real_custom_dip_proof_runner_packet(
    *,
    run_mode: str = REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
    proof_root: Path,
    readiness_packet: Mapping[str, Any],
    auth_session_readiness_packet: Mapping[str, Any] | None = None,
    api_backed_gate_required: bool = False,
    probe_codex_app_server_requested: bool = False,
    hook_readiness_probe_codex_app_server: bool = False,
    hook_readiness_probe_codex_app_server_auto_enabled: bool = False,
    auth_session_file_sha256: str = "",
    auth_session_file_written: bool = False,
    runtime_context: Mapping[str, Any],
    context_metadata: Mapping[str, Any],
    run_summaries: Sequence[Mapping[str, Any]],
    manifest_packet: Mapping[str, Any],
    manifest_file_sha256: str,
    manifest_file_written: bool,
    runner_packet_file_written: bool,
    requested_prompt_digest: str,
    required_runs: int,
    input_failures: Sequence[str],
    readiness_failures: Sequence[str],
    artifact_failures: Sequence[str],
    secret_values: Sequence[str],
) -> dict[str, Any]:
    mode = _normalize_run_mode(run_mode) or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF
    auth_session = dict(auth_session_readiness_packet or {})
    api_backed_gate_failures = _api_backed_custom_codex_gate_failures(
        auth_session,
        required=api_backed_gate_required,
    )
    readiness_failures = sorted(
        set(list(readiness_failures) + list(api_backed_gate_failures))
    )
    working_flow_delivery_required = not (
        api_backed_gate_required and mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
    )
    repeatability_failures = _repeatability_failures(
        run_summaries,
        required_runs=required_runs,
        require_working_flow_delivery=working_flow_delivery_required,
    )
    freshness_failures = [
        reason
        for reason in repeatability_failures
        if reason.endswith("hook_ledger_not_fresh")
    ]
    ledger_failures = [
        reason for reason in repeatability_failures if "ledger" in reason
    ]
    dip_failures = [
        reason for reason in repeatability_failures if "wbp_dip" in reason
    ]
    join_failures = [
        reason for reason in repeatability_failures if "join" in reason
    ]
    delivery_failures = [
        reason
        for reason in repeatability_failures
        if "delivery" in reason
        or "working_flow" in reason
        or "assistant_response" in reason
        or "handoff" in reason
    ]
    unsafe_payload = {
        "manifest": dict(manifest_packet),
        "runs": [dict(run) for run in run_summaries],
        "requested_prompt_digest": requested_prompt_digest,
    }
    unsafe_failures = []
    if packets.command_packet_has_secret_leak(unsafe_payload, secret_values=list(secret_values)):
        unsafe_failures.append("runner_secret_leak")
    if not _hex_sha256(manifest_file_sha256) or not manifest_file_written:
        artifact_failures = sorted(set(list(artifact_failures) + ["manifest_not_written"]))
    machine_error = _machine_error_code(
        input_failures=input_failures,
        readiness_failures=readiness_failures,
        freshness_failures=freshness_failures,
        ledger_failures=ledger_failures,
        dip_failures=dip_failures,
        join_failures=join_failures,
        delivery_failures=delivery_failures,
        repeatability_failures=repeatability_failures,
        unsafe_failures=unsafe_failures,
        artifact_failures=artifact_failures,
    )
    ok = machine_error == REAL_CUSTOM_DIP_PROOF_RUNNER_OK
    admission_ok = bool(ok and mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF)
    work_ok = bool(ok and mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK)
    run_count = len(run_summaries)
    prompt_digests = [_hex_sha256(run.get("prompt_digest")) for run in run_summaries]
    first_run = run_summaries[0] if run_summaries else {}
    changed_files = []
    if auth_session_file_written:
        changed_files.append(str(proof_root / CUSTOM_CODEX_AUTH_SESSION_READINESS_FILE_NAME))
    changed_files.extend(
        [
            str(proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_FILE_NAME),
            str(proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_FILE_NAME),
        ]
    )
    api_backed_gate_ok = bool(api_backed_gate_required and not api_backed_gate_failures)
    api_backed_flow_proven = bool(
        work_ok
        and api_backed_gate_ok
        and first_run.get("custom_codex_flow_proven") is True
        and first_run.get("user_prompt_submit_hook_ran") is True
        and first_run.get("delegate_to_dip_proven") is True
        and first_run.get("api_lane_called") is True
        and first_run.get("route_bound_dispatch_proven") is True
        and first_run.get("live_result_available") is True
        and first_run.get("positive_api_route_response_gate_satisfied") is True
        and first_run.get("wbp_dip_full_work_mode") is True
    )
    custom_codex_dip_feature_ready = api_backed_flow_proven
    extra = {
        **dict(context_metadata),
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND,
        "proof_scope": _proof_scope_for_mode(mode),
        "operator_command_mode": mode,
        "operator_command_surface": "wild-boar-proxy codex-runner real-custom-dip-proof",
        "proof_mode_admission_proven": admission_ok,
        "work_mode_proven": work_ok,
        "work_mode_cannot_mint_admission_proof": (
            mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
        ),
        "api_backed_custom_codex_gate_required": api_backed_gate_required,
        "working_flow_delivery_required": working_flow_delivery_required,
        "working_flow_delivery_required_for_api_backed_feature": bool(
            working_flow_delivery_required or not api_backed_gate_required
        ),
        "working_flow_delivery_nonblocking_for_api_backed_feature": bool(
            not working_flow_delivery_required and api_backed_gate_required
        ),
        "working_flow_delivery_attempted": bool(
            _safe_text(first_run.get("working_flow_delivery_machine_error_code"), limit=128)
        ),
        "probe_codex_app_server_requested": bool(probe_codex_app_server_requested),
        "hook_readiness_probe_codex_app_server": bool(
            hook_readiness_probe_codex_app_server
        ),
        "hook_readiness_probe_codex_app_server_auto_enabled": bool(
            hook_readiness_probe_codex_app_server_auto_enabled
        ),
        "api_backed_custom_codex_auth_session_proven": api_backed_gate_ok,
        "api_backed_custom_codex_flow_proven": api_backed_flow_proven,
        "api_backed_custom_codex_flow_is_not_ui_session": bool(
            api_backed_gate_required
        ),
        "custom_codex_dip_feature_ready": custom_codex_dip_feature_ready,
        "feature_ready": custom_codex_dip_feature_ready,
        "feature_ready_mode": (
            "api_key_backed_custom_codex_dip"
            if custom_codex_dip_feature_ready
            else "blocked"
        ),
        "feature_ready_does_not_require_ui_session": bool(api_backed_gate_required),
        "feature_ready_does_not_prove_product_ready": True,
        "auth_session_packet_kind": _safe_text(
            auth_session.get("packet_kind"),
            limit=96,
        ),
        "auth_session_machine_error_code": _safe_text(
            auth_session.get("machine_error_code"),
            limit=128,
        ),
        "auth_session_state": _safe_text(auth_session.get("session_state"), limit=80),
        "auth_session_api_key_only": auth_session.get("api_key_only") is True,
        "api_key_only": auth_session.get("api_key_only") is True,
        "api_key_only_counts_as_ui_session": False,
        "auth_session_logged_in_ui_session_proven": (
            auth_session.get("logged_in_ui_session_proven") is True
        ),
        "logged_in_ui_session_proven": (
            auth_session.get("logged_in_ui_session_proven") is True
        ),
        "custom_codex_ui_session_ready": (
            auth_session.get("logged_in_ui_session_proven") is True
        ),
        "auth_session_hook_ready": (
            auth_session.get("user_prompt_submit_hook_ready") is True
        ),
        "auth_session_expected_user_data_observed": (
            auth_session.get("expected_custom_user_data_dir_observed") is True
        ),
        "auth_session_app_server_bound_to_expected_user_data": (
            auth_session.get("app_server_account_bound_to_expected_user_data") is True
        ),
        "auth_session_file_written": auth_session_file_written,
        "auth_session_file_sha256": _hex_sha256(auth_session_file_sha256),
        "auth_session_file_path_recorded": False,
        "api_backed_custom_codex_gate_failures": api_backed_gate_failures,
        "real_custom_codex_hook_origin_dip_proof_proven": admission_ok,
        "repeatable_real_custom_dip_proof_proven": admission_ok,
        "custom_codex_flow_proven": bool(ok and first_run.get("custom_codex_flow_proven") is True),
        "user_prompt_submit_hook_ran": bool(ok and first_run.get("user_prompt_submit_hook_ran") is True),
        "hook_prompt_digest_bound": bool(ok and first_run.get("hook_prompt_digest_bound") is True),
        "hook_runtime_context_digest_bound": bool(
            ok and first_run.get("hook_runtime_context_digest_bound") is True
        ),
        "delegate_to_dip_proven": bool(ok and first_run.get("delegate_to_dip_proven") is True),
        "api_lane_called": bool(ok and first_run.get("api_lane_called") is True),
        "route_bound_dispatch_proven": bool(
            ok and first_run.get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": bool(ok and first_run.get("live_result_available") is True),
        "direct_provider_auth_proven": bool(
            ok and first_run.get("direct_provider_auth_proven") is True
        ),
        "direct_provider_response_observed": bool(
            ok and first_run.get("direct_provider_response_observed") is True
        ),
        "provider_auth_ok": bool(ok and first_run.get("provider_auth_ok") is True),
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": False,
        "positive_provider_proof_gate_satisfied": bool(
            ok and first_run.get("positive_provider_proof_gate_satisfied") is True
        ),
        "server_owned_bridge_or_file_bridge_response_proven": bool(
            ok and first_run.get("server_owned_bridge_or_file_bridge_response_proven") is True
        ),
        "api_route_live_response_proven": bool(
            ok and first_run.get("api_route_live_response_proven") is True
        ),
        "positive_api_route_response_gate_satisfied": bool(
            ok and first_run.get("positive_api_route_response_gate_satisfied") is True
        ),
        "live_result_bridge_or_file_bridge_used": (
            first_run.get("live_result_bridge_or_file_bridge_used") is True
        ),
        "first_run_custom_codex_flow_proven": first_run.get("custom_codex_flow_proven") is True,
        "first_run_user_prompt_submit_hook_ran": first_run.get("user_prompt_submit_hook_ran") is True,
        "first_run_hook_prompt_digest_bound": first_run.get("hook_prompt_digest_bound") is True,
        "first_run_hook_runtime_context_digest_bound": (
            first_run.get("hook_runtime_context_digest_bound") is True
        ),
        "first_run_delegate_to_dip_proven": first_run.get("delegate_to_dip_proven") is True,
        "first_run_api_lane_called": first_run.get("api_lane_called") is True,
        "first_run_route_bound_dispatch_proven": (
            first_run.get("route_bound_dispatch_proven") is True
        ),
        "first_run_live_result_available": first_run.get("live_result_available") is True,
        "first_run_direct_provider_auth_proven": (
            first_run.get("direct_provider_auth_proven") is True
        ),
        "first_run_direct_provider_response_observed": (
            first_run.get("direct_provider_response_observed") is True
        ),
        "first_run_positive_provider_proof_gate_satisfied": (
            first_run.get("positive_provider_proof_gate_satisfied") is True
        ),
        "first_run_server_owned_bridge_or_file_bridge_response_proven": (
            first_run.get("server_owned_bridge_or_file_bridge_response_proven") is True
        ),
        "first_run_api_route_live_response_proven": (
            first_run.get("api_route_live_response_proven") is True
        ),
        "first_run_positive_api_route_response_gate_satisfied": (
            first_run.get("positive_api_route_response_gate_satisfied") is True
        ),
        "first_run_codex_working_flow_delivery_proven": (
            first_run.get("codex_working_flow_delivery_proven") is True
        ),
        "first_run_approved_delivery_surface_proven": (
            first_run.get("approved_delivery_surface_proven") is True
        ),
        "first_run_assistant_response_bound_to_handoff_digest": (
            first_run.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "first_run_live_result_bridge_or_file_bridge_used": (
            first_run.get("live_result_bridge_or_file_bridge_used") is True
        ),
        "first_run_wbp_dip_work_mode": _safe_text(
            first_run.get("wbp_dip_work_mode"),
            limit=40,
        ),
        "first_run_wbp_dip_full_work_mode": (
            first_run.get("wbp_dip_full_work_mode") is True
        ),
        "first_run_wbp_dip_live_result_text_limit": int(
            first_run.get("wbp_dip_live_result_text_limit")
            if isinstance(first_run.get("wbp_dip_live_result_text_limit"), int)
            else 0
        ),
        "first_run_wbp_dip_live_result_output_token_limit": int(
            first_run.get("wbp_dip_live_result_output_token_limit")
            if isinstance(first_run.get("wbp_dip_live_result_output_token_limit"), int)
            else 0
        ),
        "first_run_wbp_dip_repo_bridge_max_steps": int(
            first_run.get("wbp_dip_repo_bridge_max_steps")
            if isinstance(first_run.get("wbp_dip_repo_bridge_max_steps"), int)
            else 0
        ),
        "work_mode_uses_full_dip_work_mode": bool(
            work_ok and first_run.get("wbp_dip_full_work_mode") is True
        ),
        "proof_mode_uses_standard_dip_work_mode": bool(
            admission_ok and first_run.get("wbp_dip_work_mode") == "standard"
        ),
        "first_run_ledger_machine_error_code": _safe_text(
            first_run.get("ledger_machine_error_code"),
            limit=128,
        ),
        "first_run_wbp_dip_machine_error_code": _safe_text(
            first_run.get("wbp_dip_machine_error_code"),
            limit=128,
        ),
        "first_run_live_result_machine_error_code": _safe_text(
            first_run.get("live_result_machine_error_code"),
            limit=128,
        ),
        "first_run_live_result_source": _safe_text(
            first_run.get("live_result_source"),
            limit=128,
        ),
        "first_run_join_machine_error_code": _safe_text(
            first_run.get("join_machine_error_code"),
            limit=128,
        ),
        "first_run_working_flow_delivery_machine_error_code": _safe_text(
            first_run.get("working_flow_delivery_machine_error_code"),
            limit=128,
        ),
        "partial_first_run_diagnostics_recorded": bool(first_run),
        "partial_first_run_diagnostics_are_not_product_ready": True,
        "required_run_count": required_runs,
        "run_count": run_count,
        "two_runs_proven": bool(
            admission_ok
            and run_count == 2
            and required_runs == 2
        ),
        "single_work_run_proven": bool(
            work_ok
            and run_count == 1
            and required_runs == 1
        ),
        "fresh_hook_ledgers_proven": bool(
            ok and all(run.get("hook_ledger_fresh") is True for run in run_summaries)
        ),
        "prompt_digests_distinct": bool(
            run_count == len(set(prompt_digests)) and all(prompt_digests)
        ),
        "proof_artifacts_distinct": bool(
            ok
            and len(
                {
                    run.get("working_flow_delivery_file_sha256")
                    for run in run_summaries
                    if _hex_sha256(run.get("working_flow_delivery_file_sha256"))
                }
            )
            == run_count
        ),
        "source_packet_hashes_present": bool(
            ok
            and all(
                _hex_sha256(run.get("ledger_proof_file_sha256"))
                and _hex_sha256(run.get("wbp_dip_file_sha256"))
                and _hex_sha256(run.get("join_file_sha256"))
                and _hex_sha256(run.get("working_flow_source_file_sha256"))
                and _hex_sha256(run.get("working_flow_delivery_file_sha256"))
                for run in run_summaries
            )
        ),
        "requested_prompt_digest": _hex_sha256(requested_prompt_digest),
        "effective_prompt_digests": prompt_digests if ok else [],
        "runtime_context_digest": runtime_context_digest(runtime_context) if ok else "",
        "runtime_context_file_path_recorded": False,
        "hook_readiness_status": _safe_text(readiness_packet.get("status"), limit=32),
        "hook_readiness_machine_error_code": _safe_text(
            readiness_packet.get("machine_error_code"),
            limit=128,
        ),
        "hook_readiness_file_sha256": _hex_sha256(
            next(
                (
                    item.get("file_sha256")
                    for item in [
                        _packet_file_summary(
                            HOOK_READINESS_FILE_NAME,
                            proof_root / HOOK_READINESS_FILE_NAME,
                            readiness_packet,
                        )
                    ]
                ),
                "",
            )
        ),
        "manifest_file_written": manifest_file_written,
        "manifest_file_sha256": _hex_sha256(manifest_file_sha256),
        "manifest_file_path_recorded": False,
        "runner_packet_file_written": runner_packet_file_written,
        "runner_packet_file_path_recorded": False,
        "proof_dir_present": proof_root.exists(),
        "proof_dir_path_recorded": False,
        "runs": [dict(run) for run in run_summaries] if ok else [],
        "run_summaries_recorded": bool(ok),
        "source_file_unforgeable": False,
        "cryptographic_origin_proven": False,
        "does_not_prove_source_file_unforgeable": True,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": bool(
            ok and first_run.get("codex_working_flow_delivery_proven") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and first_run.get("approved_delivery_surface_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            ok and first_run.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "live_result_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "roadmap_recorded": False,
        "future_plan_recorded": False,
        "next_contour_recorded": False,
        "input_failures": sorted(set(input_failures)),
        "readiness_failures": sorted(set(readiness_failures)),
        "freshness_failures": sorted(set(freshness_failures)),
        "ledger_failures": sorted(set(ledger_failures)),
        "wbp_dip_failures": sorted(set(dip_failures)),
        "join_failures": sorted(set(join_failures)),
        "delivery_failures": sorted(set(delivery_failures)),
        "repeatability_failures": sorted(set(repeatability_failures)),
        "unsafe_failures": sorted(set(unsafe_failures)),
        "artifact_failures": sorted(set(artifact_failures)),
        "blocking_reasons": sorted(
            set(
                list(input_failures)
                + list(readiness_failures)
                + list(freshness_failures)
                + list(ledger_failures)
                + list(dip_failures)
                + list(join_failures)
                + list(delivery_failures)
                + list(repeatability_failures)
                + list(unsafe_failures)
                + list(artifact_failures)
            )
        ),
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            (
                "WBP proved repeatable real Custom Codex hook-origin DIP dispatch and working-flow delivery."
                if mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF
                else "WBP completed one proof-backed DIP operator work run."
            )
            if ok
            else (
                "WBP blocked real Custom Codex DIP operator work run."
                if mode == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
                else "WBP blocked repeatable real Custom Codex DIP proof runner."
            )
        ),
        machine_error_code=machine_error,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values),
        extra=extra,
    )


def run_real_custom_dip_proof_runner_command(
    *,
    paths: RuntimePaths,
    prompt_text: object = "",
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    custom_user_data_dir: str | None = None,
    expected_alias: str = "DIP",
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
    run_count: int | None = None,
    run_mode: str = REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
    api_backed_gate_required: bool = False,
) -> dict[str, Any]:
    mode = _normalize_run_mode(run_mode)
    required_runs = _required_runs_for_mode(mode or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF)
    selected_run_count = required_runs if run_count is None else int(run_count)
    base_prompt = _safe_text(prompt_text, limit=4096)
    proof_root = _proof_root(paths, proof_dir)
    requested_prompt_digest = _sha256_text(base_prompt) if base_prompt else ""
    repo_root = _repo_root_from_cwd(codex_cwd)
    codex_executable = (
        Path(codex_bin).expanduser()
        if codex_bin
        else default_codex_bin({"WBP_PROFILE_DIR": str(paths.profile_dir)})
    )
    model = _safe_text(codex_model or DEFAULT_MODEL, limit=80) or DEFAULT_MODEL
    selected_sandbox = _safe_text(sandbox or DEFAULT_SANDBOX, limit=80) or DEFAULT_SANDBOX
    alias = _safe_text(expected_alias, limit=80) or "DIP"
    context_path = runtime_context_path(paths=paths)
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    run_session_id = _run_session_id()
    secret_values = [
        base_prompt,
        *[
            _effective_prompt(base_prompt, i, run_session_id)
            for i in range(1, selected_run_count + 1)
            if base_prompt
        ],
    ]
    secret_values.extend(_runtime_secret_values(runtime_context))

    input_failures: list[str] = []
    if not mode:
        input_failures.append("run_mode_invalid")
    if mode in {
        REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
        REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    } and not base_prompt:
        input_failures.append("prompt_required")
    if not codex_executable.is_file() or not os.access(codex_executable, os.X_OK):
        input_failures.append("codex_binary_not_executable")
    if not (repo_root / "tools" / "wbp_dip").is_file():
        input_failures.append("wbp_dip_tool_missing")
    if context_metadata.get("runtime_context_file_read") is not True:
        input_failures.append("runtime_context_file_not_read")
    if selected_run_count != required_runs:
        input_failures.append("run_count_must_match_mode")

    proof_root.mkdir(parents=True, exist_ok=True)
    artifact_failures: list[str] = []
    auth_session_readiness_packet: dict[str, Any] = {}
    auth_session_file_sha256 = ""
    auth_session_file_written = False
    if api_backed_gate_required:
        auth_session_readiness_packet = run_custom_codex_auth_session_readiness_command(
            paths=paths,
            custom_user_data_dir=custom_user_data_dir,
            probe_hook_readiness=True,
            probe_account_app_server=True,
        )
        auth_session_file = proof_root / CUSTOM_CODEX_AUTH_SESSION_READINESS_FILE_NAME
        try:
            _write_artifact(auth_session_file, auth_session_readiness_packet)
            auth_session_file_sha256 = _sha256_file(auth_session_file)
            auth_session_file_written = bool(auth_session_file_sha256)
        except (OSError, TypeError, ValueError):
            artifact_failures.append("auth_session_readiness_write_failed")
    explicit_hook_hash = _safe_text(codex_hook_current_hash, limit=80)
    # Default live proof runs to the app-server truth surface unless the operator
    # intentionally pins the current hook hash.
    hook_readiness_probe_codex_app_server = bool(
        probe_codex_app_server or not explicit_hook_hash
    )
    hook_readiness_probe_codex_app_server_auto_enabled = bool(
        not probe_codex_app_server and not explicit_hook_hash
    )
    hook_hash = explicit_hook_hash if explicit_hook_hash else ""
    readiness_packet = build_user_prompt_submit_readiness_packet(
        paths=paths,
        codex_hook_current_hash=hook_hash,
        probe_codex_app_server=hook_readiness_probe_codex_app_server,
    )
    readiness_file = proof_root / HOOK_READINESS_FILE_NAME
    try:
        _write_artifact(readiness_file, readiness_packet)
    except (OSError, TypeError, ValueError):
        artifact_failures.append("readiness_write_failed")
    readiness_failures = _readiness_failures(readiness_packet)
    readiness_failures = sorted(
        set(
            readiness_failures
            + _api_backed_custom_codex_gate_failures(
                auth_session_readiness_packet,
                required=api_backed_gate_required,
            )
        )
    )

    runs: list[dict[str, Any]] = []
    if not input_failures and not readiness_failures and not artifact_failures:
        for index in range(1, selected_run_count + 1):
            runs.append(
                _run_once(
                    paths=paths,
                    run_dir=proof_root / f"run-{index:02d}",
                    prompt_text=_effective_prompt(base_prompt, index, run_session_id),
                    codex_bin=codex_executable,
                    repo_root=repo_root,
                    model=model,
                    sandbox=selected_sandbox,
                    expected_alias=alias,
                    timeout_seconds=timeout_seconds,
                    codex_hook_current_hash=hook_hash,
                    probe_codex_app_server=hook_readiness_probe_codex_app_server,
                    run_mode=mode or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
                )
            )
            if runs[-1].get("run_blocking_reasons"):
                break

    run_summaries = [_run_summary(index, run) for index, run in enumerate(runs, start=1)]
    provisional_repeatability_failures = _repeatability_failures(
        run_summaries,
        required_runs=selected_run_count,
    )
    provisional_delivery_failures = [
        reason
        for reason in provisional_repeatability_failures
        if "delivery" in reason
        or "working_flow" in reason
        or "assistant_response" in reason
        or "handoff" in reason
    ]
    provisional_error = _machine_error_code(
        input_failures=input_failures,
        readiness_failures=readiness_failures,
        freshness_failures=[],
        ledger_failures=[],
        dip_failures=[],
        join_failures=[],
        delivery_failures=provisional_delivery_failures,
        repeatability_failures=provisional_repeatability_failures,
        unsafe_failures=[],
        artifact_failures=artifact_failures,
    )
    manifest_packet = _build_manifest(
        run_mode=mode or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
        readiness_packet=readiness_packet,
        run_summaries=run_summaries,
        runner_status="ok" if provisional_error == REAL_CUSTOM_DIP_PROOF_RUNNER_OK else "error",
        runner_machine_error_code=provisional_error,
    )
    manifest_path = proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_FILE_NAME
    manifest_file_sha256 = ""
    manifest_file_written = False
    try:
        _write_artifact(manifest_path, manifest_packet)
        manifest_file_sha256 = _sha256_file(manifest_path)
        manifest_file_written = bool(manifest_file_sha256)
    except (OSError, TypeError, ValueError):
        artifact_failures.append("manifest_write_failed")

    runner_packet = build_real_custom_dip_proof_runner_packet(
        proof_root=proof_root,
        readiness_packet=readiness_packet,
        auth_session_readiness_packet=auth_session_readiness_packet,
        api_backed_gate_required=api_backed_gate_required,
        probe_codex_app_server_requested=probe_codex_app_server,
        hook_readiness_probe_codex_app_server=hook_readiness_probe_codex_app_server,
        hook_readiness_probe_codex_app_server_auto_enabled=(
            hook_readiness_probe_codex_app_server_auto_enabled
        ),
        auth_session_file_sha256=auth_session_file_sha256,
        auth_session_file_written=auth_session_file_written,
        run_mode=mode or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
        runtime_context=runtime_context,
        context_metadata=context_metadata,
        run_summaries=run_summaries,
        manifest_packet=manifest_packet,
        manifest_file_sha256=manifest_file_sha256,
        manifest_file_written=manifest_file_written,
        runner_packet_file_written=True,
        requested_prompt_digest=requested_prompt_digest,
        required_runs=selected_run_count,
        input_failures=input_failures,
        readiness_failures=readiness_failures,
        artifact_failures=artifact_failures,
        secret_values=secret_values,
    )
    runner_file = proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_FILE_NAME
    try:
        _write_artifact(runner_file, runner_packet)
    except (OSError, TypeError, ValueError):
        artifact_failures.append("runner_write_failed")
        runner_packet = build_real_custom_dip_proof_runner_packet(
            proof_root=proof_root,
            readiness_packet=readiness_packet,
            auth_session_readiness_packet=auth_session_readiness_packet,
            api_backed_gate_required=api_backed_gate_required,
            probe_codex_app_server_requested=probe_codex_app_server,
            hook_readiness_probe_codex_app_server=hook_readiness_probe_codex_app_server,
            hook_readiness_probe_codex_app_server_auto_enabled=(
                hook_readiness_probe_codex_app_server_auto_enabled
            ),
            auth_session_file_sha256=auth_session_file_sha256,
            auth_session_file_written=auth_session_file_written,
            run_mode=mode or REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_PROOF,
            runtime_context=runtime_context,
            context_metadata=context_metadata,
            run_summaries=run_summaries,
            manifest_packet=manifest_packet,
            manifest_file_sha256=manifest_file_sha256,
            manifest_file_written=manifest_file_written,
            runner_packet_file_written=False,
            requested_prompt_digest=requested_prompt_digest,
            required_runs=selected_run_count,
            input_failures=input_failures,
            readiness_failures=readiness_failures,
            artifact_failures=artifact_failures,
            secret_values=secret_values,
        )
    return runner_packet
