# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Isolated Kimi one-shot CLI layer (B11_CODE).

Builds on the B09 generic one-shot runtime: `KIMI_CODE_HOME` isolation,
immutable-snapshot repo-read enforcement (OS read-only sandbox or immutable
snapshot is required for `repo_read`; otherwise Kimi is limited to `none`),
denied-write proof via real OS EACCES on snapshot files, auth isolation,
output normalization, and timeout / cancel proof. Real Kimi CLI binary probe
is B11_LIVE scope; all B11_CODE evidence is fake-adapter controlled and
declared-not-live. One-shot sessions never resume.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from . import one_shot_cli_runtime as osr
from .runtime import build_command_payload

KIMI_CLI_TOOL_ID = "kimi-cli"
KIMI_CODE_HOME_ENV = "KIMI_CODE_HOME"
KIMI_PROVIDER_ID = "kimi"

# Snapshot bounds: a server-owned immutable copy of the project for repo
# read. VCS dirs are excluded; oversized projects fail closed.
SNAPSHOT_MAX_FILES = 500
SNAPSHOT_MAX_TOTAL_BYTES = 10 * 1024 * 1024
SNAPSHOT_EXCLUDED_DIRS = (".git", ".hg", ".svn")

KIMI_READ_MODE_SNAPSHOT = "immutable_snapshot"
KIMI_READ_MODE_NONE = "none"
KIMI_WRITE_MODE_DEFAULT = "denied"

KIMI_OK = "OK"
KIMI_SNAPSHOT_FAILED = "KIMI_SNAPSHOT_FAILED"
KIMI_SNAPSHOT_UNAVAILABLE = "KIMI_SNAPSHOT_UNAVAILABLE"
KIMI_READ_DENIED = "KIMI_REPO_READ_DENIED"
KIMI_WRITE_DENIED = "KIMI_REPO_WRITE_DENIED"
KIMI_SESSION_INVALID = "KIMI_SESSION_INVALID"


@dataclass(frozen=True)
class KimiSnapshot:
    root: Path
    file_count: int
    total_bytes: int
    digest_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "digest_sha256": self.digest_sha256,
        }


def _snapshot_digest(root: Path) -> str:
    """Content-only digest over snapshot files (relative paths sorted)."""
    hasher = hashlib.sha256()
    for rel in sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()):
        hasher.update(rel.encode("utf-8"))
        with open(root / rel, "rb") as fh:
            hasher.update(fh.read())
    return hasher.hexdigest()


def create_kimi_snapshot(
    project_root: Path | str,
    *,
    snapshot_root: Path | str | None = None,
    runtime: osr.OneShotRuntime | None = None,
    max_files: int = SNAPSHOT_MAX_FILES,
    max_total_bytes: int = SNAPSHOT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Create a server-owned immutable snapshot of the project.

    Files are chmod 0444, dirs 0555, so writes must fail with a real
    EACCES. Bounded by file count and total bytes; failure fails closed.
    Without an explicit snapshot root the scratch location is derived from
    the engine instance's sealed homes root; without an engine instance
    the production facade answers fail-closed.
    """
    project = Path(project_root)
    if not project.is_dir():
        return build_command_payload(
            ok=False,
            human_message="project root is not a directory.",
            machine_error_code=KIMI_SNAPSHOT_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"project_root": str(project)},
        )
    snapshot = Path(snapshot_root) if snapshot_root is not None else None
    if snapshot is None:
        if runtime is None:
            return osr.default_production_facade().run(KIMI_CLI_TOOL_ID)
        snapshot = Path(
            tempfile_under_homes(runtime, "kimi-snapshot", project.name)
        )
    if snapshot.exists():
        shutil.rmtree(snapshot)
    changed: list[str] = []
    try:
        snapshot.mkdir(parents=True, exist_ok=True)
        changed.append(str(snapshot))
        file_count = 0
        total_bytes = 0
        for current, dirs, files in os.walk(project):
            dirs[:] = [d for d in dirs if d not in SNAPSHOT_EXCLUDED_DIRS]
            rel_dir = Path(current).relative_to(project)
            target_dir = snapshot / rel_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in files:
                source = Path(current) / name
                target = target_dir / name
                try:
                    shutil.copy2(source, target)
                except OSError as exc:
                    return build_command_payload(
                        ok=False,
                        human_message=f"snapshot copy failed: {exc}",
                        machine_error_code=KIMI_SNAPSHOT_FAILED,
                        liveness="healthy",
                        severity="error",
                        operator_action="user_action",
                        changed_files=changed,
                        exit_code=1,
                        extra={"source": str(source)},
                    )
                size = target.stat().st_size
                file_count += 1
                total_bytes += size
                changed.append(str(target))
                if file_count > max_files:
                    return build_command_payload(
                        ok=False,
                        human_message="snapshot exceeded max file count.",
                        machine_error_code=KIMI_SNAPSHOT_FAILED,
                        liveness="healthy",
                        severity="error",
                        operator_action="user_action",
                        changed_files=changed,
                        exit_code=1,
                        extra={"file_count": file_count, "max_files": max_files},
                    )
                if total_bytes > max_total_bytes:
                    return build_command_payload(
                        ok=False,
                        human_message="snapshot exceeded max total size.",
                        machine_error_code=KIMI_SNAPSHOT_FAILED,
                        liveness="healthy",
                        severity="error",
                        operator_action="user_action",
                        changed_files=changed,
                        exit_code=1,
                        extra={"total_bytes": total_bytes, "max_total_bytes": max_total_bytes},
                    )
        for current, dirs, files in os.walk(snapshot):
            for name in dirs:
                os.chmod(Path(current) / name, 0o555)
            for name in files:
                os.chmod(Path(current) / name, 0o444)
        os.chmod(snapshot, 0o555)
    except OSError as exc:
        return build_command_payload(
            ok=False,
            human_message=f"snapshot creation failed: {exc}",
            machine_error_code=KIMI_SNAPSHOT_FAILED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=changed,
            exit_code=1,
            extra={"snapshot_root": str(snapshot)},
        )
    snap = KimiSnapshot(
        root=snapshot,
        file_count=file_count,
        total_bytes=total_bytes,
        digest_sha256=_snapshot_digest(snapshot),
    )
    return build_command_payload(
        ok=True,
        human_message=f"kimi snapshot ready ({file_count} files).",
        machine_error_code=KIMI_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=changed,
        exit_code=0,
        extra={
            "snapshot": snap.to_dict(),
            "repo_read_policy": KIMI_READ_MODE_SNAPSHOT,
            "files_read_only": True,
            "dirs_read_only": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def tempfile_under_homes(runtime: osr.OneShotRuntime, subdir: str, name: str) -> Path:
    """Snapshot scratch under the engine instance's sealed homes root."""
    root = runtime.homes_root / subdir
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{name}-{int(time.time() * 1000)}"


def kimi_one_shot_session(
    *,
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Create the isolated Kimi one-shot session with auth isolation.

    R5: without an explicit engine instance the production facade is used,
    which is fail-closed (`CLI_DISABLED_PENDING_SECURITY_ADMISSION`)
    before any filesystem or process side effect. Tests pass their own
    `OneShotRuntime` built from `tests/fakes.py`.
    """
    if runtime is None:
        return osr.default_production_facade().session(KIMI_PROVIDER_ID)
    home_result = runtime.create_provider_home(KIMI_PROVIDER_ID)
    if home_result["status"] != "ok":
        return home_result
    home = Path(home_result["home_path"])
    runtime.one_shot_auth_session(KIMI_PROVIDER_ID, home)
    auth_status = runtime.one_shot_auth_status(home)
    sandbox = osr.probe_os_sandbox()
    return build_command_payload(
        ok=True,
        human_message="Kimi one-shot session ready (isolated home).",
        machine_error_code=KIMI_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "provider_id": KIMI_PROVIDER_ID,
            "tool_id": KIMI_CLI_TOOL_ID,
            "kimi_code_home": str(home),
            "auth_present": auth_status.get("auth_present", False),
            "auth_presence_only": True,
            "repo_write_policy": KIMI_WRITE_MODE_DEFAULT,
            "repo_read_policy": KIMI_READ_MODE_NONE,
            "os_enforcement": sandbox["os_enforcement"],
            "os_sandbox_available": sandbox["os_sandbox_available"],
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def _kimi_provider_env(
    session: dict[str, Any],
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Provider env mapping for the Kimi child (F08 fix: actually passed
    to the engine as `provider_env`, never built and discarded)."""
    home = Path(session["kimi_code_home"])
    env: dict[str, str] = {KIMI_CODE_HOME_ENV: str(home)}
    if snapshot is not None:
        env["KIMI_SNAPSHOT_ROOT"] = str(snapshot["root"])
    return env


def kimi_one_shot_run(
    text: str,
    *,
    session: dict[str, Any],
    runtime: osr.OneShotRuntime | None = None,
    args: Sequence[str] = (),
    timeout_seconds: float = osr.DEFAULT_RUN_TIMEOUT_SECONDS,
    output_cap_bytes: int = osr.DEFAULT_OUTPUT_CAP_BYTES,
    cancel_after_seconds: float | None = None,
) -> dict[str, Any]:
    """Run the Kimi one-shot CLI with the kimi provider environment.

    Without an explicit engine instance the production facade answers
    fail-closed.
    """
    if session.get("kimi_code_home") is None:
        return build_command_payload(
            ok=False,
            human_message="kimi session is not initialized.",
            machine_error_code=KIMI_SESSION_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"tool_id": KIMI_CLI_TOOL_ID},
        )
    if runtime is None:
        return osr.default_production_facade().run(KIMI_CLI_TOOL_ID)
    run = runtime.one_shot_cli_run(
        KIMI_CLI_TOOL_ID,
        args=("--respond", text, *args),
        provider_home=Path(session["kimi_code_home"]),
        provider_env=_kimi_provider_env(session),
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
            "kimi one-shot response ok." if run["status"] == "ok"
            else "kimi one-shot run failed."
        ),
        machine_error_code=run["machine_error_code"],
        liveness="healthy",
        severity="info" if run["status"] == "ok" else "error",
        operator_action="none" if run["status"] == "ok" else "user_action",
        changed_files=[],
        exit_code=run.get("exit_code"),
        extra={
            "tool_id": KIMI_CLI_TOOL_ID,
            "run": run.get("run"),
            "parsed_output": parsed,
            "kimi_code_home": session.get("kimi_code_home"),
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def kimi_text_proof(
    text: str,
    *,
    session: dict[str, Any],
    expected_prefix: str = "",
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Text response proof via the fake adapter (declared-not-live)."""
    run = kimi_one_shot_run(text, session=session, runtime=runtime)
    stdout = (run.get("run") or {}).get("stdout", "")
    ok = run["status"] == "ok" and bool(stdout.strip())
    if expected_prefix:
        ok = ok and stdout.startswith(expected_prefix)
    return build_command_payload(
        ok=ok,
        human_message="kimi text proof ok." if ok else "kimi text proof failed.",
        machine_error_code=KIMI_OK if ok else run["machine_error_code"],
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=0 if ok else 1,
        extra={
            "tool_id": KIMI_CLI_TOOL_ID,
            "text_received": bool(stdout.strip()),
            "expected_prefix_match": stdout.startswith(expected_prefix) if expected_prefix else None,
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def kimi_repo_read_policy(
    *,
    session: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Repo-read policy: immutable snapshot when one exists, else none.

    Kimi never claims an OS read-only sandbox that is absent; the snapshot
    is the only admitted read surface in B11_CODE.
    """
    if snapshot is not None:
        return build_command_payload(
            ok=True,
            human_message="kimi repo read admitted via immutable snapshot.",
            machine_error_code=KIMI_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "repo_read_policy": KIMI_READ_MODE_SNAPSHOT,
                "snapshot": snapshot.get("snapshot"),
                "resume_supported": False,
                "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
            },
        )
    return build_command_payload(
        ok=False,
        human_message="kimi repo read denied: no OS sandbox, no snapshot.",
        machine_error_code=KIMI_READ_DENIED,
        liveness="healthy",
        severity="error",
        operator_action="user_action",
        changed_files=[],
        exit_code=1,
        extra={
            "repo_read_policy": KIMI_READ_MODE_NONE,
            "reason": "repo_read requires an OS read-only sandbox or immutable snapshot",
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def kimi_repo_read_proof(
    *,
    session: dict[str, Any],
    snapshot: dict[str, Any],
    snapshot_path: Path | str,
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Repo-read proof: the fake adapter reads only a snapshot path.

    The path must live inside the snapshot root; reads outside the
    snapshot fail closed.
    """
    snap_root = Path(snapshot["snapshot"]["root"]).resolve()
    target = Path(snapshot_path).resolve()
    try:
        target.relative_to(snap_root)
    except ValueError:
        return build_command_payload(
            ok=False,
            human_message="read path is outside the snapshot; denied.",
            machine_error_code=KIMI_READ_DENIED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "snapshot_root": str(snap_root),
                "requested_path": str(target),
                "resume_supported": False,
                "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
            },
        )
    if not target.is_file():
        return build_command_payload(
            ok=False,
            human_message="snapshot path is not a file.",
            machine_error_code=KIMI_READ_DENIED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"snapshot_path": str(target)},
        )
    if runtime is None:
        return osr.default_production_facade().run(KIMI_CLI_TOOL_ID)
    run = runtime.one_shot_cli_run(
        KIMI_CLI_TOOL_ID,
        args=("--read-file", str(target)),
        provider_home=Path(session["kimi_code_home"]),
        provider_env=_kimi_provider_env(session, snapshot=snapshot["snapshot"]),
    )
    stdout = (run.get("run") or {}).get("stdout", "")
    expected = target.read_text(encoding="utf-8")
    ok = run["status"] == "ok" and stdout.strip() == expected.strip()
    return build_command_payload(
        ok=ok,
        human_message="kimi repo-read proof ok." if ok else "kimi repo-read proof failed.",
        machine_error_code=KIMI_OK if ok else run["machine_error_code"],
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        exit_code=0 if ok else 1,
        extra={
            "snapshot_path": str(target),
            "content_matches_snapshot_file": ok,
            "snapshot_digest_sha256": snapshot["snapshot"]["digest_sha256"],
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "repo_read_policy": KIMI_READ_MODE_SNAPSHOT,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def kimi_denied_write_proof(
    *,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Denied-write proof with real OS evidence.

    Writing to a snapshot file must raise EACCES (files are 0444); the
    observed OSError errno is the evidence, not a policy claim.
    """
    snap = snapshot.get("snapshot") or {}
    root = Path(snap.get("root", ""))
    target = None
    if root.is_dir():
        files = sorted(p for p in root.rglob("*") if p.is_file())
        if files:
            target = files[0]
    if target is None:
        return build_command_payload(
            ok=False,
            human_message="no snapshot file to test write denial.",
            machine_error_code=KIMI_SNAPSHOT_UNAVAILABLE,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"resume_supported": False, "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON},
        )
    errno_observed: int | None = None
    error_name: str | None = None
    try:
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("x")
    except OSError as exc:
        errno_observed = exc.errno
        error_name = exc.strerror or ""
    ok = errno_observed is not None and errno_observed == 13  # EACCES
    return build_command_payload(
        ok=ok,
        human_message=(
            "kimi denied-write proof ok (OS EACCES on snapshot file)."
            if ok else "kimi denied-write proof failed (file was writable!)."
        ),
        machine_error_code=KIMI_OK if ok else KIMI_WRITE_DENIED,
        liveness="healthy",
        severity="info" if ok else "error",
        operator_action="none" if ok else "stop",
        changed_files=[],
        exit_code=0 if ok else 1,
        extra={
            "snapshot_path": str(target),
            "observed_errno": errno_observed,
            "observed_error": error_name,
            "expected_errno": 13,
            "repo_write_policy": KIMI_WRITE_MODE_DEFAULT,
            "evidence": "os_eacces_observed",
            "proof_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )


def kimi_timeout_cancel_proof(
    *,
    session: dict[str, Any],
    cancel_after_seconds: float | None = None,
    timeout_seconds: float | None = None,
    runtime: osr.OneShotRuntime | None = None,
) -> dict[str, Any]:
    """Timeout / cancel proof: bounded runtime terminates the whole group."""
    if cancel_after_seconds is None and timeout_seconds is None:
        raise ValueError("one of cancel_after_seconds or timeout_seconds is required")
    if runtime is None:
        return osr.default_production_facade().run(KIMI_CLI_TOOL_ID)
    run = runtime.one_shot_cli_run(
        KIMI_CLI_TOOL_ID,
        args=("--sleep", "30"),
        provider_home=Path(session["kimi_code_home"]),
        provider_env=_kimi_provider_env(session),
        timeout_seconds=timeout_seconds if timeout_seconds is not None else 30.0,
        cancel_after_seconds=cancel_after_seconds,
    )
    run_payload = run.get("run") or {}
    ok = run["status"] == "error" and (
        run_payload.get("cancelled") or run_payload.get("timed_out")
    )
    return build_command_payload(
        ok=ok,
        human_message="kimi timeout/cancel proof ok." if ok else "kimi timeout/cancel proof failed.",
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


def build_kimi_one_shot_receipt() -> dict[str, Any]:
    """Declared receipt for the Kimi one-shot layer (B11_CODE)."""
    return build_command_payload(
        ok=True,
        human_message="Kimi one-shot CLI layer declared; fake-adapter proof only (B11_CODE).",
        machine_error_code="SYNTHETIC_PROVEN",
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "tool_id": KIMI_CLI_TOOL_ID,
            "declared_not_live_verified": True,
            "kimi_code_home_env": KIMI_CODE_HOME_ENV,
            "repo_read_policy": KIMI_READ_MODE_NONE,
            "repo_read_requires": "os_read_only_sandbox_or_immutable_snapshot",
            "repo_write_policy": KIMI_WRITE_MODE_DEFAULT,
            "snapshot_max_files": SNAPSHOT_MAX_FILES,
            "snapshot_max_total_bytes": SNAPSHOT_MAX_TOTAL_BYTES,
            "resume_supported": False,
            "resume_reason": osr.ONE_SHOT_NO_RESUME_REASON,
        },
    )
