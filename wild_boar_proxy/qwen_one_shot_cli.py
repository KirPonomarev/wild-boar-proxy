# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Isolated Qwen one-shot CLI layer (B10_CODE).

Builds on the B09 generic one-shot runtime: `QWEN_HOME` / `QWEN_RUNTIME_DIR`
isolation, project-config denial/admission (`.qwen`, `.env`, extensions,
plugins default-denied unless individually admitted and digested), permission
controls (repo write denied by default), text / repo-read proof, denied-write
proof, and timeout / cancel proof. Real Qwen CLI binary probe is B10_LIVE
scope; all B10_CODE evidence is fake-adapter controlled and declared-not-live.
One-shot sessions never resume.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from . import one_shot_cli_runtime as osr
from .runtime import build_command_payload

QWEN_CLI_TOOL_ID = "qwen-cli"
QWEN_HOME_ENV = "QWEN_HOME"
QWEN_RUNTIME_DIR_ENV = "QWEN_RUNTIME_DIR"
QWEN_PROVIDER_ID = "qwen"

# Project configs that are default-denied unless individually admitted
# with a digest. Admission records live in the provider home.
QWEN_PROJECT_DENIED_NAMES = (".qwen", ".env", "extensions", "plugins")
QWEN_ADMISSIONS_FILENAME = "project-config-admissions.json"

QWEN_READ_MODE_DEFAULT = "none"
QWEN_WRITE_MODE_DEFAULT = "denied"

QWEN_OK = "OK"
QWEN_CONFIG_DENIED = "QWEN_PROJECT_CONFIG_DENIED"
QWEN_CONFIG_ADMISSION_MISSING = "QWEN_PROJECT_CONFIG_ADMISSION_MISSING"
QWEN_CONFIG_DIGEST_MISMATCH = "QWEN_PROJECT_CONFIG_DIGEST_MISMATCH"
QWEN_WRITE_DENIED = "QWEN_REPO_WRITE_DENIED"
QWEN_SESSION_INVALID = "QWEN_SESSION_INVALID"


def _canonical(obj: Any) -> bytes:
    return (
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _admissions_file(provider_home: Path) -> Path:
    return Path(provider_home) / QWEN_ADMISSIONS_FILENAME


def read_project_admissions(provider_home: Path) -> dict[str, str]:
    """path -> sha256 digest; missing/invalid file means no admissions."""
    path = _admissions_file(provider_home)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    records = payload.get("admissions", {})
    if not isinstance(records, dict):
        return {}
    return {str(k): str(v) for k, v in records.items()}


def _write_project_admissions(provider_home: Path, admissions: dict[str, str]) -> None:
    path = _admissions_file(provider_home)
    payload = {"schema_version": 1, "admissions": dict(sorted(admissions.items()))}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    os.chmod(path, 0o600)


def admit_project_config(
    provider_home: Path | str,
    path: Path | str,
    *,
    digest: str | None = None,
) -> dict[str, Any]:
    """Admit one project config path with its sha256 digest.

    The digest is computed from the file content when not supplied.
    Admission is recorded in the provider home (server-side).
    """
    home = Path(provider_home)
    config_path = Path(path)
    if digest is None:
        try:
            digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
        except OSError as exc:
            return build_command_payload(
                ok=False,
                human_message=f"cannot digest project config: {exc}",
                machine_error_code=QWEN_CONFIG_ADMISSION_MISSING,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"config_path": str(config_path), "admitted": False},
            )
    admissions = read_project_admissions(home)
    admissions[str(config_path)] = digest
    changed = [str(_admissions_file(home))]
    try:
        _write_project_admissions(home, admissions)
    except OSError as exc:
        return build_command_payload(
            ok=False,
            human_message=f"admission write failed: {exc}",
            machine_error_code=QWEN_CONFIG_ADMISSION_MISSING,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"config_path": str(config_path), "admitted": False},
        )
    return build_command_payload(
        ok=True,
        human_message=f"project config admitted for {config_path.name}.",
        machine_error_code=QWEN_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=changed,
        exit_code=0,
        extra={
            "config_path": str(config_path),
            "digest_sha256": digest,
            "admitted": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def deny_project_config(
    provider_home: Path | str,
    path: Path | str,
) -> dict[str, Any]:
    """Remove an admission (config returns to default-denied)."""
    home = Path(provider_home)
    admissions = read_project_admissions(home)
    config_path = str(Path(path))
    removed = admissions.pop(config_path, None) is not None
    changed = [str(_admissions_file(home))]
    _write_project_admissions(home, admissions)
    return build_command_payload(
        ok=True,
        human_message=(
            f"admission removed for {Path(config_path).name}." if removed
            else "no admission existed."
        ),
        machine_error_code=QWEN_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=changed if removed else [],
        exit_code=0,
        extra={
            "config_path": config_path,
            "removed": removed,
            "default_denied": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def project_config_policy(
    provider_home: Path | str,
    project_root: Path | str,
) -> dict[str, Any]:
    """Evaluate the project-config policy for a project root.

    Every known config name under the project root is default-denied; an
    admission requires a matching digest of the current file content.
    """
    home = Path(provider_home)
    root = Path(project_root)
    admissions = read_project_admissions(home)
    decisions: list[dict[str, Any]] = []
    for name in QWEN_PROJECT_DENIED_NAMES:
        candidate = root / name
        if not candidate.exists():
            continue
        if candidate.is_file():
            current_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            admitted_digest = admissions.get(str(candidate))
            if admitted_digest is None:
                decision = "denied"
                code = QWEN_CONFIG_ADMISSION_MISSING
            elif admitted_digest != current_digest:
                decision = "denied"
                code = QWEN_CONFIG_DIGEST_MISMATCH
            else:
                decision = "admitted"
                code = QWEN_OK
            decisions.append(
                {
                    "config_path": str(candidate),
                    "config_name": name,
                    "decision": decision,
                    "machine_error_code": code,
                    "current_digest_sha256": current_digest,
                    "admitted_digest_sha256": admitted_digest,
                }
            )
        else:
            decisions.append(
                {
                    "config_path": str(candidate),
                    "config_name": name,
                    "decision": "denied",
                    "machine_error_code": QWEN_CONFIG_DENIED,
                    "reason": "directory config is never admitted in B10_CODE",
                    "current_digest_sha256": None,
                    "admitted_digest_sha256": None,
                }
            )
    denied = [d for d in decisions if d["decision"] == "denied"]
    return build_command_payload(
        ok=not denied,
        human_message=(
            "project config policy ok." if not denied else
            f"{len(denied)} project config(s) denied."
        ),
        machine_error_code=QWEN_OK if not denied else QWEN_CONFIG_DENIED,
        liveness="healthy",
        severity="info" if not denied else "error",
        operator_action="none" if not denied else "user_action",
        changed_files=[],
        exit_code=0 if not denied else 1,
        extra={
            "project_root": str(root),
            "default_denied_names": list(QWEN_PROJECT_DENIED_NAMES),
            "decisions": decisions,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def qwen_one_shot_session(
    *,
    homes_root: Path | str | None = None,
) -> dict[str, Any]:
    """Create the isolated Qwen one-shot session.

    Provider home (0700) with `QWEN_HOME` and `QWEN_RUNTIME_DIR` pointing
    inside it, plus a presence-only auth session. Never touches the real
    user home.
    """
    home_result = osr.create_provider_home(QWEN_PROVIDER_ID, homes_root=homes_root)
    if home_result["status"] != "ok":
        return home_result
    home = Path(home_result["home_path"])
    runtime_dir = Path(home_result["runtime_dir"])
    osr.one_shot_auth_session(QWEN_PROVIDER_ID, home)
    auth_status = osr.one_shot_auth_status(home)
    return build_command_payload(
        ok=True,
        human_message="Qwen one-shot session ready (isolated home).",
        machine_error_code=QWEN_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "provider_id": QWEN_PROVIDER_ID,
            "tool_id": QWEN_CLI_TOOL_ID,
            "qwen_home": str(home),
            "qwen_runtime_dir": str(runtime_dir),
            "auth_present": auth_status.get("auth_present", False),
            "auth_presence_only": True,
            "repo_write_policy": QWEN_WRITE_MODE_DEFAULT,
            "repo_read_policy": QWEN_READ_MODE_DEFAULT,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def _qwen_environment(
    session: dict[str, Any],
    *,
    project_root: Path | str | None = None,
) -> dict[str, str]:
    """Sterile environment with QWEN_HOME / QWEN_RUNTIME_DIR inside the
    isolated provider home; the project root is never added to PATH or HOME.
    """
    home = Path(session["qwen_home"])
    runtime_dir = Path(session["qwen_runtime_dir"])
    env = osr.build_sterile_environment(provider_home=home)
    env[QWEN_HOME_ENV] = str(home)
    env[QWEN_RUNTIME_DIR_ENV] = str(runtime_dir)
    if project_root is not None:
        env["QWEN_PROJECT_ROOT"] = str(Path(project_root))
    return env


def qwen_one_shot_run(
    text: str,
    *,
    session: dict[str, Any],
    project_root: Path | str | None = None,
    args: Sequence[str] = (),
    timeout_seconds: float = osr.DEFAULT_RUN_TIMEOUT_SECONDS,
    output_cap_bytes: int = osr.DEFAULT_OUTPUT_CAP_BYTES,
    cancel_after_seconds: float | None = None,
) -> dict[str, Any]:
    """Run the Qwen one-shot CLI with the qwen environment.

    Output is normalized through the generic parser (`auto` profile).
    """
    if session.get("qwen_home") is None:
        return build_command_payload(
            ok=False,
            human_message="qwen session is not initialized.",
            machine_error_code=QWEN_SESSION_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": QWEN_CLI_TOOL_ID},
        )
    env = _qwen_environment(session, project_root=project_root)
    run = osr.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--respond", text, *args),
        stdin_text=None,
        provider_home=Path(session["qwen_home"]),
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
        cancel_after_seconds=cancel_after_seconds,
        env=env,
        _test_internal=True,
    )
    parsed = None
    if run["status"] == "ok":
        parsed = osr.parse_cli_output(run.get("run", {}).get("stdout", ""), profile="auto")
    return build_command_payload(
        ok=run["status"] == "ok",
        human_message=(
            "qwen one-shot response ok." if run["status"] == "ok"
            else "qwen one-shot run failed."
        ),
        machine_error_code=run["machine_error_code"],
        liveness="healthy",
        severity="info" if run["status"] == "ok" else "error",
        operator_action="none" if run["status"] == "ok" else "user_action",
        changed_files=[],
        exit_code=run.get("exit_code"),
        extra={
            "tool_id": QWEN_CLI_TOOL_ID,
            "run": run.get("run"),
            "parsed_output": parsed,
            "qwen_home": session.get("qwen_home"),
            "qwen_runtime_dir": session.get("qwen_runtime_dir"),
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def qwen_text_proof(
    text: str,
    *,
    session: dict[str, Any],
    expected_prefix: str = "",
) -> dict[str, Any]:
    """Text response proof: the fake adapter echoes the prompt; the packet
    proves a positive text response without any live claim."""
    run = qwen_one_shot_run(text, session=session)
    stdout = (run.get("run") or {}).get("stdout", "")
    ok = run["status"] == "ok" and bool(stdout.strip())
    if expected_prefix:
        ok = ok and stdout.startswith(expected_prefix)
    return build_command_payload(
        ok=ok,
        human_message="qwen text proof ok." if ok else "qwen text proof failed.",
        machine_error_code=QWEN_OK if ok else run["machine_error_code"],
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=0 if ok else 1,
        extra={
            "tool_id": QWEN_CLI_TOOL_ID,
            "text_received": bool(stdout.strip()),
            "expected_prefix_match": stdout.startswith(expected_prefix) if expected_prefix else None,
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def qwen_repo_read_proof(
    *,
    session: dict[str, Any],
    project_root: Path | str,
    config_path: Path | str,
) -> dict[str, Any]:
    """Repo-read proof for an admitted project config.

    The config must first be admitted with a digest; the fake adapter reads
    only the admitted path and returns its content. Digest mismatch fails
    closed. Policy is honest: repo read mode is `none` at the policy layer;
    this proof exercises the explicit per-path admission only.
    """
    home = Path(session["qwen_home"])
    policy = project_config_policy(home, project_root)
    admission = next(
        (
            d for d in policy.get("decisions", [])
            if d.get("config_path") == str(Path(config_path))
        ),
        None,
    )
    if admission is None or admission["decision"] != "admitted":
        return build_command_payload(
            ok=False,
            human_message="config is not admitted; repo read denied.",
            machine_error_code=QWEN_CONFIG_ADMISSION_MISSING,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "config_path": str(config_path),
                "decision": admission.get("decision") if admission else "not_scanned",
                "repo_read_policy": QWEN_READ_MODE_DEFAULT,
                "resume_supported": False,
                "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
            },
        )
    env = _qwen_environment(session, project_root=project_root)
    run = osr.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--read-file", str(config_path)),
        provider_home=home,
        env=env,
        _test_internal=True,
    )
    stdout = (run.get("run") or {}).get("stdout", "")
    expected = Path(config_path).read_text(encoding="utf-8")
    ok = run["status"] == "ok" and stdout.strip() == expected.strip()
    return build_command_payload(
        ok=ok,
        human_message="qwen repo-read proof ok." if ok else "qwen repo-read proof failed.",
        machine_error_code=QWEN_OK if ok else run["machine_error_code"],
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=0 if ok else 1,
        extra={
            "config_path": str(config_path),
            "admitted_digest_sha256": admission["admitted_digest_sha256"],
            "content_matches_admitted_file": ok,
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "repo_read_policy": QWEN_READ_MODE_DEFAULT,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def qwen_denied_write_proof(
    *,
    session: dict[str, Any],
    project_root: Path | str,
) -> dict[str, Any]:
    """Denied-write proof: the permission policy denies repo write by
    default. The packet is honest about OS enforcement: policy-level denial
    is reported as such and never claims an OS sandbox that is absent.
    """
    sandbox = osr.probe_os_sandbox()
    return build_command_payload(
        ok=True,
        human_message="qwen repo write is denied by policy (no OS sandbox claim).",
        machine_error_code=QWEN_WRITE_DENIED,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "repo_write_policy": QWEN_WRITE_MODE_DEFAULT,
            "denied_by": "permission_policy",
            "os_enforcement": sandbox["os_enforcement"],
            "os_sandbox_available": sandbox["os_sandbox_available"],
            "project_root": str(project_root),
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def qwen_timeout_cancel_proof(
    *,
    session: dict[str, Any],
    cancel_after_seconds: float | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Timeout / cancel proof: the fake adapter sleeps; the bounded runtime
    must terminate the whole process group."""
    if cancel_after_seconds is None and timeout_seconds is None:
        raise ValueError("one of cancel_after_seconds or timeout_seconds is required")
    run = osr.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--sleep", "30"),
        provider_home=Path(session["qwen_home"]),
        timeout_seconds=timeout_seconds if timeout_seconds is not None else 30.0,
        cancel_after_seconds=cancel_after_seconds,
        env=_qwen_environment(session),
        _test_internal=True,
    )
    run_payload = run.get("run") or {}
    ok = run["status"] == "error" and (
        run_payload.get("cancelled") or run_payload.get("timed_out")
    )
    return build_command_payload(
        ok=ok,
        human_message="qwen timeout/cancel proof ok." if ok else "qwen timeout/cancel proof failed.",
        machine_error_code=run["machine_error_code"],
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=run.get("exit_code"),
        extra={
            "cancelled": run_payload.get("cancelled"),
            "timed_out": run_payload.get("timed_out"),
            "machine_error_code": run["machine_error_code"],
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def build_qwen_one_shot_receipt() -> dict[str, Any]:
    """Declared receipt for the Qwen one-shot layer (B10_CODE)."""
    return build_command_payload(
        ok=True,
        human_message="Qwen one-shot CLI layer declared; fake-adapter proof only (B10_CODE).",
        machine_error_code="SYNTHETIC_PROVEN",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "tool_id": QWEN_CLI_TOOL_ID,
            "declared_not_live_verified": True,
            "qwen_home_env": QWEN_HOME_ENV,
            "qwen_runtime_dir_env": QWEN_RUNTIME_DIR_ENV,
            "project_denied_names": list(QWEN_PROJECT_DENIED_NAMES),
            "repo_write_policy": QWEN_WRITE_MODE_DEFAULT,
            "repo_read_policy": QWEN_READ_MODE_DEFAULT,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )
