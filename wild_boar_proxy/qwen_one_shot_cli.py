# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Isolated Qwen one-shot CLI layer (B10_CODE).

Builds on the B09 generic one-shot runtime: `QWEN_HOME` / `QWEN_RUNTIME_DIR`
isolation, project-config denial/admission (`.qwen`, `.env`, extensions,
plugins default-denied unless individually admitted and digested), permission
controls (repo write denied by default), text / repo-read proof, denied-write
proof, and timeout / cancel proof. R61 adds the server-owned production
headless adapter while exact binary admission, auth configuration, and real
provider proof remain B10_LIVE. Test adapters remain controlled and
declared-not-live. One-shot sessions never resume.
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
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Create the isolated Qwen one-shot session.

    R5: without an explicit engine instance the production facade is used,
    which is fail-closed (`CLI_DISABLED_PENDING_SECURITY_ADMISSION`)
    before any filesystem or process side effect. Tests pass their own
    `OneShotRuntime` built from `tests/fakes.py`. There is no
    caller-selectable homes root anywhere in production.
    """
    if runtime is None:
        return osr.default_production_facade().session(QWEN_PROVIDER_ID)
    home_result = runtime.create_provider_home(QWEN_PROVIDER_ID)
    if home_result["status"] != "ok":
        return home_result
    home = Path(home_result["home_path"])
    runtime_dir = Path(home_result["runtime_dir"])
    runtime.one_shot_auth_session(QWEN_PROVIDER_ID, home)
    auth_status = runtime.one_shot_auth_status(home)
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


def _qwen_provider_env(
    session: dict[str, Any],
    *,
    project_root: Path | str | None = None,
) -> dict[str, str]:
    """Provider env mapping for the Qwen child.

    R5/F08 fix: this mapping is passed to the engine as `provider_env`
    and actually reaches the child process; it is never just built and
    discarded. The engine validates keys against the provider allowlist
    and the sandbox profile enforces real access.
    """
    home = Path(session["qwen_home"])
    runtime_dir = Path(session["qwen_runtime_dir"])
    env: dict[str, str] = {
        QWEN_HOME_ENV: str(home),
        QWEN_RUNTIME_DIR_ENV: str(runtime_dir),
        **osr.QWEN_FIXED_ENV,
    }
    if project_root is not None:
        env["QWEN_PROJECT_ROOT"] = str(Path(project_root))
    return env


def qwen_one_shot_run(
    text: str,
    *,
    session: dict[str, Any],
    runtime: osr.OneShotRuntime | None = None,
    project_root: Path | str | None = None,
    args: Sequence[str] = (),
    timeout_seconds: float = osr.DEFAULT_RUN_TIMEOUT_SECONDS,
    output_cap_bytes: int = osr.DEFAULT_OUTPUT_CAP_BYTES,
    cancel_after_seconds: float | None = None,
) -> dict[str, Any]:
    """Run the Qwen one-shot CLI with the qwen provider environment.

    Without an explicit engine instance the production facade answers
    fail-closed. Output is normalized through the generic parser
    (`auto` profile).
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
    if args:
        return build_command_payload(
            ok=False,
            human_message="caller-supplied Qwen argv is not admitted.",
            machine_error_code=osr.ONE_SHOT_SCHEMA_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": QWEN_CLI_TOOL_ID, "caller_argv_blocked": True},
        )
    if runtime is None:
        return osr.default_production_facade().run_prompt(
            QWEN_CLI_TOOL_ID,
            text,
            active_project_root=project_root,
        )
    provider_env = _qwen_provider_env(session, project_root=project_root)
    run = runtime.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--prompt", text, *osr.QWEN_OPERATIONAL_ARGS),
        stdin_text=None,
        provider_home=Path(session["qwen_home"]),
        provider_env=provider_env,
        timeout_seconds=timeout_seconds,
        output_cap_bytes=output_cap_bytes,
        cancel_after_seconds=cancel_after_seconds,
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
        changed_files=run.get("changed_files", []),
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


def _qwen_response_text(parsed: dict[str, Any]) -> str:
    """Extract response text from Qwen's JSON document without inventing it."""
    document = parsed.get("document")
    candidates: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            response = value.get("response")
            if isinstance(response, str):
                candidates.append(response)
            result = value.get("result")
            if (
                value.get("type") == "result"
                and value.get("is_error") is False
                and isinstance(result, str)
            ):
                candidates.append(result)
            if value.get("type") == "text" and isinstance(value.get("text"), str):
                candidates.append(value["text"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    return "\n".join(item for item in candidates if item.strip())


def qwen_text_proof(
    text: str,
    *,
    session: dict[str, Any],
    expected_prefix: str = "",
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Text response proof: the fake adapter echoes the prompt; the packet
    proves a positive text response without any live claim."""
    run = qwen_one_shot_run(text, session=session, runtime=runtime)
    response_text = _qwen_response_text(run.get("parsed_output") or {})
    ok = run["status"] == "ok" and bool(response_text.strip())
    if expected_prefix:
        ok = ok and response_text.startswith(expected_prefix)
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
            "text_received": bool(response_text.strip()),
            "expected_prefix_match": (
                response_text.startswith(expected_prefix) if expected_prefix else None
            ),
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
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Repo-read proof for an admitted project config.

    The config must first be admitted with a digest; the fake adapter reads
    only the admitted path and returns its content. Digest mismatch fails
    closed. Policy is honest: repo read mode is `none` at the policy layer;
    this proof exercises the explicit per-path admission only.
    """
    home = Path(session["qwen_home"])
    # Canonicalize the read target: seatbelt matches the kernel-resolved
    # path, and the child must request the resolved path. The target must
    # stay inside the declared project root (containment), not merely carry
    # an admission digest recorded for some other location.
    root_resolved = Path(project_root).resolve()
    target = Path(config_path).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return build_command_payload(
            ok=False,
            human_message="read path is outside the project root; denied.",
            machine_error_code=QWEN_CONFIG_ADMISSION_MISSING,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "config_path": str(config_path),
                "decision": "outside_project_root",
                "repo_read_policy": QWEN_READ_MODE_DEFAULT,
                "resume_supported": False,
                "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
            },
        )
    policy = project_config_policy(home, project_root)
    admission = next(
        (
            d for d in policy.get("decisions", [])
            if Path(d.get("config_path", "")).resolve() == target
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
    if runtime is None:
        return osr.default_production_facade().run(QWEN_CLI_TOOL_ID)
    provider_env = _qwen_provider_env(session, project_root=project_root)
    run = runtime.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--read-file", str(target)),
        provider_home=home,
        provider_env=provider_env,
    )
    stdout = (run.get("run") or {}).get("stdout", "")
    expected = target.read_text(encoding="utf-8")
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
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Timeout / cancel proof: the fake adapter sleeps; the bounded runtime
    must terminate the whole process group."""
    if cancel_after_seconds is None and timeout_seconds is None:
        raise ValueError("one of cancel_after_seconds or timeout_seconds is required")
    if runtime is None:
        return osr.default_production_facade().run(QWEN_CLI_TOOL_ID)
    run = runtime.one_shot_cli_run(
        QWEN_CLI_TOOL_ID,
        args=("--sleep", "30"),
        provider_home=Path(session["qwen_home"]),
        provider_env=_qwen_provider_env(session),
        timeout_seconds=timeout_seconds if timeout_seconds is not None else 30.0,
        cancel_after_seconds=cancel_after_seconds,
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
    """Declared code receipt for the Qwen one-shot production adapter."""
    return build_command_payload(
        ok=True,
        human_message=(
            "Qwen one-shot production adapter code declared; exact binary, "
            "auth, and provider proof remain B10_LIVE."
        ),
        machine_error_code="B10_CODE_PRODUCTION_ADAPTER_DECLARED",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "tool_id": QWEN_CLI_TOOL_ID,
            "declared_not_live_verified": True,
            "provider_adapter_admitted": True,
            "binary_live_admitted": False,
            "auth_live_admitted": False,
            "provider_live_proven": False,
            "b10_live_pending": True,
            "headless_argv_schema": list(osr.QWEN_ALLOWED_ARGV_SCHEMA),
            "output_parser": "json_document_or_text",
            "network_policy": osr.QWEN_NETWORK_POLICY,
            "qwen_home_env": QWEN_HOME_ENV,
            "qwen_runtime_dir_env": QWEN_RUNTIME_DIR_ENV,
            "project_denied_names": list(QWEN_PROJECT_DENIED_NAMES),
            "repo_write_policy": QWEN_WRITE_MODE_DEFAULT,
            "repo_read_policy": QWEN_READ_MODE_DEFAULT,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )
