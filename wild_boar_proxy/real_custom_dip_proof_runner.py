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

from .command_effects import EFFECT_MUTATE
from .core import packets
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
    expected_hook_trusted_hash,
    hook_command_for_paths,
    hook_ledger_path,
)
from .wbp_dip_hook_origin_proof import (
    WBP_DIP_HOOK_ORIGIN_OK,
    run_wbp_dip_hook_origin_proof_command,
)
from .wbp_dip_tool import DEFAULT_MODEL, DEFAULT_SANDBOX, default_codex_bin


REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND = "wbp_repeatable_real_custom_dip_proof_runner"
REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_PACKET_KIND = (
    "wbp_repeatable_real_custom_dip_proof_runner_manifest"
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
LEDGER_PROOF_FILE_NAME = "real-user-prompt-submit-ledger-proof.packet.json"
WBP_DIP_HOOK_ORIGIN_FILE_NAME = "wbp-dip-hook-origin-proof.packet.json"

_RUN_REQUIRED_TRUE_FIELDS = (
    "custom_codex_flow_proven",
    "user_prompt_submit_hook_ran",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "delegate_to_dip_proven",
    "api_lane_called",
    "route_bound_dispatch_proven",
    "live_result_available",
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


def _effective_prompt(base_prompt: str, run_index: int, run_session_id: str) -> str:
    marker = (
        f"WBP_REAL_CUSTOM_DIP_PROOF_RUN_{run_index:02d}_"
        f"{_sha256_text(base_prompt)[:12]}_{run_session_id}"
    )
    return (
        f"{base_prompt} "
        f"Proof run marker: {marker}. "
        "Answer shortly; do not expose route ids, secrets, or backend details."
    )


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
    for field in _RUN_REQUIRED_TRUE_FIELDS:
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
        "artifacts": [
            _packet_file_summary(LEDGER_PROOF_FILE_NAME, ledger_file, ledger_packet),
            _packet_file_summary("wbp-dip/wbp-dip-tool.packet.json", dip_file, dip_packet),
            _packet_file_summary(WBP_DIP_HOOK_ORIGIN_FILE_NAME, join_file, join_packet),
        ],
        "run_blocking_reasons": join_failures,
    }


def _run_summary(run_index: int, run: Mapping[str, Any]) -> dict[str, Any]:
    join = run.get("join_packet")
    join_packet = join if isinstance(join, Mapping) else {}
    ledger = run.get("ledger_proof_packet")
    ledger_packet = ledger if isinstance(ledger, Mapping) else {}
    dip = run.get("wbp_dip_packet")
    dip_packet = dip if isinstance(dip, Mapping) else {}
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
    return {
        "run_index": run_index,
        "prompt_digest": _hex_sha256(run.get("prompt_digest")),
        "hook_ledger_fresh": run.get("hook_ledger_fresh") is True,
        "custom_codex_flow_proven": custom_codex_flow_proven,
        "user_prompt_submit_hook_ran": user_prompt_submit_hook_ran,
        "hook_prompt_digest_bound": hook_prompt_digest_bound,
        "hook_runtime_context_digest_bound": hook_runtime_context_digest_bound,
        "delegate_to_dip_proven": delegate_to_dip_proven,
        "api_lane_called": api_lane_called,
        "route_bound_dispatch_proven": route_bound_dispatch_proven,
        "live_result_available": live_result_available,
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


def _repeatability_failures(run_summaries: Sequence[Mapping[str, Any]], *, required_runs: int) -> list[str]:
    failures: list[str] = []
    if len(run_summaries) != required_runs:
        failures.append("required_run_count_not_met")
    prompt_digests = [_hex_sha256(run.get("prompt_digest")) for run in run_summaries]
    if len(set(prompt_digests)) != len(prompt_digests):
        failures.append("prompt_digests_not_distinct")
    for index, run in enumerate(run_summaries, start=1):
        if run.get("blocking_reasons"):
            failures.extend(
                f"run_{index}_{reason}"
                for reason in run.get("blocking_reasons", [])
                if packets.is_command_value_token(str(reason))
            )
        if run.get("hook_ledger_fresh") is not True:
            failures.append(f"run_{index}_hook_ledger_not_fresh")
        for field in _RUN_REQUIRED_TRUE_FIELDS:
            if run.get(field) is not True:
                failures.append(f"run_{index}_{field}_not_true")
        for field in _RUN_REQUIRED_FALSE_FIELDS:
            if run.get(field) is not False:
                failures.append(f"run_{index}_{field}_not_false")
        for field in ("ledger_proof_file_sha256", "wbp_dip_file_sha256", "join_file_sha256"):
            if not _hex_sha256(run.get(field)):
                failures.append(f"run_{index}_{field}_missing")
    return sorted(set(failures))


def _build_manifest(
    *,
    readiness_packet: Mapping[str, Any],
    run_summaries: Sequence[Mapping[str, Any]],
    runner_status: str,
    runner_machine_error_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_PACKET_KIND,
        "proof_scope": "repeatable_real_custom_codex_hook_origin_to_wbp_dip_live_dispatch",
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
    if repeatability_failures:
        return REAL_CUSTOM_DIP_PROOF_RUNNER_REPEATABILITY_FAILED
    return REAL_CUSTOM_DIP_PROOF_RUNNER_OK


def build_real_custom_dip_proof_runner_packet(
    *,
    proof_root: Path,
    readiness_packet: Mapping[str, Any],
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
    repeatability_failures = _repeatability_failures(
        run_summaries,
        required_runs=required_runs,
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
        repeatability_failures=repeatability_failures,
        unsafe_failures=unsafe_failures,
        artifact_failures=artifact_failures,
    )
    ok = machine_error == REAL_CUSTOM_DIP_PROOF_RUNNER_OK
    run_count = len(run_summaries)
    prompt_digests = [_hex_sha256(run.get("prompt_digest")) for run in run_summaries]
    first_run = run_summaries[0] if run_summaries else {}
    changed_files = [
        str(proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_FILE_NAME),
        str(proof_root / REAL_CUSTOM_DIP_PROOF_RUNNER_FILE_NAME),
    ]
    extra = {
        **dict(context_metadata),
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND,
        "proof_scope": "repeatable_real_custom_codex_hook_origin_to_wbp_dip_live_dispatch",
        "real_custom_codex_hook_origin_dip_proof_proven": ok,
        "repeatable_real_custom_dip_proof_proven": ok,
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
        "partial_first_run_diagnostics_recorded": bool(first_run),
        "partial_first_run_diagnostics_are_not_product_ready": True,
        "required_run_count": required_runs,
        "run_count": run_count,
        "two_runs_proven": bool(ok and run_count == required_runs),
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
                    run.get("join_file_sha256")
                    for run in run_summaries
                    if _hex_sha256(run.get("join_file_sha256"))
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
        "codex_working_flow_delivery_proven": False,
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
            "WBP proved repeatable real Custom Codex UserPromptSubmit hook origin to DIP API dispatch."
            if ok
            else "WBP blocked repeatable real Custom Codex DIP proof runner."
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
    prompt_text: object,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    expected_alias: str = "DIP",
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
    run_count: int = 2,
) -> dict[str, Any]:
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
        *[_effective_prompt(base_prompt, i, run_session_id) for i in range(1, run_count + 1)],
    ]
    secret_values.extend(_runtime_secret_values(runtime_context))

    input_failures: list[str] = []
    if not base_prompt:
        input_failures.append("prompt_required")
    if not codex_executable.is_file() or not os.access(codex_executable, os.X_OK):
        input_failures.append("codex_binary_not_executable")
    if not (repo_root / "tools" / "wbp_dip").is_file():
        input_failures.append("wbp_dip_tool_missing")
    if context_metadata.get("runtime_context_file_read") is not True:
        input_failures.append("runtime_context_file_not_read")
    if run_count != 2:
        input_failures.append("run_count_must_be_two")

    proof_root.mkdir(parents=True, exist_ok=True)
    explicit_hook_hash = _safe_text(codex_hook_current_hash, limit=80)
    hook_hash = (
        explicit_hook_hash
        if explicit_hook_hash
        else ""
        if probe_codex_app_server
        else expected_hook_trusted_hash(hook_command_for_paths(paths))
    )
    readiness_packet = build_user_prompt_submit_readiness_packet(
        paths=paths,
        codex_hook_current_hash=hook_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    readiness_file = proof_root / HOOK_READINESS_FILE_NAME
    artifact_failures: list[str] = []
    try:
        _write_artifact(readiness_file, readiness_packet)
    except (OSError, TypeError, ValueError):
        artifact_failures.append("readiness_write_failed")
    readiness_failures = _readiness_failures(readiness_packet)

    runs: list[dict[str, Any]] = []
    if not input_failures and not readiness_failures and not artifact_failures:
        for index in range(1, run_count + 1):
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
                    probe_codex_app_server=probe_codex_app_server,
                )
            )
            if runs[-1].get("run_blocking_reasons"):
                break

    run_summaries = [_run_summary(index, run) for index, run in enumerate(runs, start=1)]
    provisional_error = _machine_error_code(
        input_failures=input_failures,
        readiness_failures=readiness_failures,
        freshness_failures=[],
        ledger_failures=[],
        dip_failures=[],
        join_failures=[],
        repeatability_failures=_repeatability_failures(run_summaries, required_runs=run_count),
        unsafe_failures=[],
        artifact_failures=artifact_failures,
    )
    manifest_packet = _build_manifest(
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
        runtime_context=runtime_context,
        context_metadata=context_metadata,
        run_summaries=run_summaries,
        manifest_packet=manifest_packet,
        manifest_file_sha256=manifest_file_sha256,
        manifest_file_written=manifest_file_written,
        runner_packet_file_written=True,
        requested_prompt_digest=requested_prompt_digest,
        required_runs=run_count,
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
            runtime_context=runtime_context,
            context_metadata=context_metadata,
            run_summaries=run_summaries,
            manifest_packet=manifest_packet,
            manifest_file_sha256=manifest_file_sha256,
            manifest_file_written=manifest_file_written,
            runner_packet_file_written=False,
            requested_prompt_digest=requested_prompt_digest,
            required_runs=run_count,
            input_failures=input_failures,
            readiness_failures=readiness_failures,
            artifact_failures=artifact_failures,
            secret_values=secret_values,
        )
    return runner_packet
