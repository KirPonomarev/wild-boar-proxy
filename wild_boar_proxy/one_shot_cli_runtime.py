# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic server-owned one-shot CLI runtime (B09 production admission).

Production authority has two independently required layers:

- an immutable code declaration describes every executable, argv,
  environment, parser, bound, process, sandbox, auth, session, and network
  surface that WBP may admit;
- a WBP-owned external admission record binds that declaration to one exact
  executable realpath, content digest, and observed version.

`OneShotRuntime` remains the sealed execution engine used by explicit test
adapters. `ProductionOneShotFacade` is the only production entry surface. It
can probe a declared executable without granting operational authority, but it
revalidates both layers immediately before every operational spawn. Qwen's and
Kimi's sealed headless contracts are admitted by R61 and R62 while binary,
auth, and live-provider authority remain external gates. No environment hook,
caller-selected path, global grant, or mutable module-level manifest exists.

Sandbox truth: every child process spawned by `OneShotRuntime` runs under
a macOS seatbelt profile built by the single production builder
`build_server_owned_sandbox_profile` (`deny default`). If `sandbox-exec`
is unavailable the runtime fails closed with `CLI_UNAVAILABLE_UNSAFE`;
there is no unsandboxed fallback. Secret values never appear in packets.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import fcntl

from . import active_project_root as active_root
from .core import packets as command_packets
from .runtime import build_command_payload
from .runtime_errors import RuntimeErrorInfo

ONE_SHOT_RUNTIME_SCHEMA_VERSION = 3
ONE_SHOT_ADMISSION_SCHEMA_VERSION = 2

# Production server-owned homes root. FIXED constant, not overridable by
# environment, config, prompt, or caller.
DEFAULT_HOMES_ROOT = (
    Path.home() / "Library" / "Application Support" / "WildBoarProxy" / "one-shot-homes"
)
DEFAULT_ADMISSION_ROOT = (
    Path.home()
    / "Library"
    / "Application Support"
    / "WildBoarProxy"
    / "one-shot-cli-admission"
)
DEFAULT_BUNDLE_ROOT = DEFAULT_ADMISSION_ROOT / "releases"
ADMISSION_FILENAME = "admissions.json"
ADMISSION_LOCK_FILENAME = "writer.lock"

DEFAULT_PROBE_TIMEOUT_SECONDS = 20.0
DEFAULT_RUN_TIMEOUT_SECONDS = 300.0
DEFAULT_OUTPUT_CAP_BYTES = 64 * 1024
DEFAULT_DIGEST_SIZE_LIMIT = 512 * 1024 * 1024
DEFAULT_BUNDLE_DIGEST_SIZE_LIMIT = 1024 * 1024 * 1024
DEFAULT_BUNDLE_FILE_COUNT_LIMIT = 100_000
CANCEL_GRACE_SECONDS = 5.0
PROCESS_GROUP_EXIT_WAIT_SECONDS = 2.0

# Fixed executable roots. These are code-owned and never inherited from the
# ambient PATH. System roots stay first for deterministic system-tool lookup;
# conventional standalone-CLI roots are explicit candidates rather than an
# authorization to search arbitrary user locations.
STERILE_PATH_ENTRIES = (
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
    str(DEFAULT_ADMISSION_ROOT / "bin"),
)

TRUSTED_BINARY_REALPATH_ROOTS = (
    "/usr",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/opt/homebrew",
    "/usr/local",
    str(Path.home() / ".local"),
    str(DEFAULT_ADMISSION_ROOT),
)

# Environment keys that must never cross into a one-shot child.
SECRET_ENV_SUFFIXES = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY", "AUTH",
)

ONE_SHOT_NO_RESUME_REASON = "one_shot_sessions_are_stateless"
QWEN_PROMPT_MAX_CHARS = 16 * 1024
QWEN_AUTH_FILENAME = ".env"
QWEN_NETWORK_POLICY = "provider_outbound"
QWEN_SANDBOX_POLICY = "deny_default_provider_network"
QWEN_AUTH_STRATEGY = "isolated_home_env_file"
QWEN_FIXED_ENV: Mapping[str, str] = MappingProxyType({
    "QWEN_USAGE_STATISTICS_ENABLED": "false",
    "QWEN_TELEMETRY_ENABLED": "false",
})

QWEN_OPERATIONAL_ARGS: tuple[str, ...] = (
    "--output-format",
    "json",
    "--safe-mode",
    "--approval-mode",
    "plan",
    "--max-session-turns",
    "30",
    "--max-wall-time",
    "300s",
    "--max-tool-calls",
    "25",
    "--exclude-tools",
    "shell,write,edit,agent",
)
QWEN_ALLOWED_ARGV_SCHEMA: tuple[str, ...] = (
    "literal:--prompt",
    "prompt:utf8_nonsecret_max_16384",
    *(f"literal:{item}" for item in QWEN_OPERATIONAL_ARGS),
)

KIMI_PROMPT_MAX_CHARS = 16 * 1024
KIMI_AUTH_FILENAME = "config.toml"
KIMI_CREDENTIALS_DIRNAME = "credentials"
KIMI_SKILLS_DIRNAME = "skills"
KIMI_NETWORK_POLICY = "provider_outbound"
KIMI_SANDBOX_POLICY = "deny_default_provider_network"
KIMI_AUTH_STRATEGY = "isolated_home_config"
KIMI_FIXED_ENV: Mapping[str, str] = MappingProxyType({
    "KIMI_DISABLE_TELEMETRY": "1",
    "KIMI_CODE_BACKGROUND_KEEP_ALIVE_ON_EXIT": "0",
    "KIMI_CODE_BACKGROUND_MAX_RUNNING_TASKS": "1",
    "KIMI_CODE_AGENT_SWARM_MAX_CONCURRENCY": "1",
    "KIMI_SUBAGENT_TIMEOUT_MS": "300000",
    "KIMI_CODE_BUILTIN_PRODUCT_SKILLS": "0",
    "KIMI_LOOP_MAX_STEPS_PER_TURN": "25",
    "KIMI_LOOP_MAX_ATTEMPTS_PER_STEP": "3",
    "KIMI_CODE_NO_AUTO_UPDATE": "1",
    "KIMI_DISABLE_CRON": "1",
})
KIMI_OPERATIONAL_ARGS: tuple[str, ...] = (
    "--output-format",
    "stream-json",
)
KIMI_ALLOWED_ARGV_SCHEMA: tuple[str, ...] = (
    "literal:--prompt",
    "prompt:utf8_nonsecret_max_16384",
    *(f"literal:{item}" for item in KIMI_OPERATIONAL_ARGS),
    "literal:--skills-dir",
    "path:sealed_empty_skills_dir",
    "optional:literal:--add-dir",
    "optional:path:validated_read_only_root",
)

# Machine error codes.
ONE_SHOT_OK = "OK"
ONE_SHOT_TOOL_UNKNOWN = "ONE_SHOT_TOOL_UNKNOWN"
TOOL_BINARY_NOT_FOUND = "TOOL_BINARY_NOT_FOUND"
ONE_SHOT_PROBE_FAILED = "ONE_SHOT_PROBE_FAILED"
ONE_SHOT_RUN_TIMEOUT = "ONE_SHOT_RUN_TIMEOUT"
ONE_SHOT_RUN_FAILED = "ONE_SHOT_RUN_FAILED"
ONE_SHOT_CANCELLED = "ONE_SHOT_CANCELLED"
ONE_SHOT_ENV_VIOLATION = "ONE_SHOT_ENV_VIOLATION"
ONE_SHOT_SCHEMA_INVALID = "ONE_SHOT_SCHEMA_INVALID"
ONE_SHOT_PATH_VIOLATION = "ONE_SHOT_PATH_VIOLATION"
CLI_DISABLED_PENDING_SECURITY_ADMISSION = "CLI_DISABLED_PENDING_SECURITY_ADMISSION"
CLI_UNAVAILABLE_UNSAFE = "CLI_UNAVAILABLE_UNSAFE"
CLI_PROVIDER_ADAPTER_NOT_ADMITTED = "CLI_PROVIDER_ADAPTER_NOT_ADMITTED"
CLI_BINARY_ADMISSION_MISSING = "CLI_BINARY_ADMISSION_MISSING"
CLI_BINARY_ADMISSION_INVALID = "CLI_BINARY_ADMISSION_INVALID"
CLI_BINARY_IDENTITY_DRIFT = "CLI_BINARY_IDENTITY_DRIFT"
CLI_ADMISSION_DIGEST_MISMATCH = "CLI_ADMISSION_DIGEST_MISMATCH"
CLI_AUTH_NOT_ADMITTED = "CLI_AUTH_NOT_ADMITTED"
CLI_NETWORK_POLICY_NOT_ADMITTED = "CLI_NETWORK_POLICY_NOT_ADMITTED"
ONE_SHOT_SECRET_INPUT_BLOCKED = "ONE_SHOT_SECRET_INPUT_BLOCKED"
ONE_SHOT_OUTPUT_INVALID = "ONE_SHOT_OUTPUT_INVALID"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
KEY_VALUE_LINE_RE = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")
ONE_SHOT_QUOTED_SECRET_PATTERNS = (
    re.compile(
        r"(?i)((?<![A-Za-z0-9_])[\"']?"
        r"(?:api[_-]?key|password|secret|token)[\"']?\s*"
        r"[:=]\s*[\"']?)[A-Za-z0-9._~+/=-]{8,}"
    ),
    re.compile(
        r"(?i)((?<![A-Za-z0-9_])[\"']?authorization[\"']?\s*"
        r"[:=]\s*[\"']?"
        r"(?:bearer\s+)?)[A-Za-z0-9._~+/=-]{8,}"
    ),
)


def _redact_one_shot_text(value: Any) -> str:
    original = str(value or "")
    redacted = str(command_packets.redact_command_packet_value(original))
    for pattern in ONE_SHOT_QUOTED_SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: match.group(1) + "<redacted>", redacted)
    return redacted


def _qwen_json_output_is_success(
    parsed: Mapping[str, Any], run_record: Mapping[str, Any]
) -> bool:
    """Accept only Qwen's complete buffered JSON success envelope."""
    if (
        parsed.get("valid") is not True
        or parsed.get("truncated") is True
        or run_record.get("stdout_truncated") is True
        or run_record.get("stderr_truncated") is True
    ):
        return False
    document = parsed.get("document")
    if not isinstance(document, list) or not document:
        return False
    return any(
        isinstance(item, dict)
        and item.get("type") == "result"
        and item.get("subtype") == "success"
        and item.get("is_error") is False
        and isinstance(item.get("result"), str)
        and bool(item["result"].strip())
        for item in document
    )


def _kimi_stream_output_is_success(
    parsed: Mapping[str, Any], run_record: Mapping[str, Any]
) -> bool:
    """Accept only a complete Kimi stream-json final assistant message."""
    if (
        parsed.get("truncated") is True
        or parsed.get("malformed_lines") != 0
        or run_record.get("stdout_truncated") is True
        or run_record.get("stderr_truncated") is True
    ):
        return False
    records = parsed.get("records")
    if not isinstance(records, list) or not records:
        return False
    if any(not isinstance(record, dict) for record in records):
        return False
    final = records[-1]
    if not isinstance(final, dict) or final.get("role") != "assistant":
        return False
    content = final.get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if not isinstance(content, list) or not content:
        return False
    return any(
        isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
        and bool(block["text"].strip())
        for block in content
    )


@dataclass(frozen=True)
class OneShotToolManifestEntry:
    """Server-owned description of an invocable CLI tool.

    A server-owned `binary_name` is resolved only through fixed candidate
    roots, or is an absolute path whose resolved owner/mode/root policy passes.
    Fake-adapter entries (`server_owned=False`) may use test-owned absolute
    paths only inside explicitly constructed engine instances.
    """

    tool_id: str
    binary_name: str
    display_name: str
    version_args: tuple[str, ...] = ("--version",)
    output_profiles: tuple[str, ...] = ("text",)
    server_owned: bool = True
    provider_id: str = "test-adapter"
    allowed_argv_schema: tuple[str, ...] = ()
    operational_args: tuple[str, ...] = ()
    allowed_environment_keys: tuple[str, ...] = ()
    cwd_policy: str = "sealed_sandbox_cwd"
    output_parser: str = "auto"
    timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES
    process_group_policy: str = "new_session_group_termination"
    sandbox_policy: str = "deny_default_offline"
    auth_strategy: str = "test_presence_only"
    session_policy: str = ONE_SHOT_NO_RESUME_REASON
    network_policy: str = "denied"
    provider_adapter_admitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "binary_name": self.binary_name,
            "display_name": self.display_name,
            "version_args": list(self.version_args),
            "output_profiles": list(self.output_profiles),
            "server_owned": self.server_owned,
            "provider_id": self.provider_id,
            "allowed_argv_schema": list(self.allowed_argv_schema),
            "operational_args": list(self.operational_args),
            "allowed_environment_keys": list(self.allowed_environment_keys),
            "cwd_policy": self.cwd_policy,
            "output_parser": self.output_parser,
            "timeout_seconds": self.timeout_seconds,
            "output_cap_bytes": self.output_cap_bytes,
            "process_group_policy": self.process_group_policy,
            "sandbox_policy": self.sandbox_policy,
            "auth_strategy": self.auth_strategy,
            "session_policy": self.session_policy,
            "network_policy": self.network_policy,
            "provider_adapter_admitted": self.provider_adapter_admitted,
        }


@dataclass(frozen=True)
class SandboxProfile:
    """Declared sandbox posture reported in packets.

    Enforcement is honest: `os_enforcement` reflects what the OS actually
    provides (probed), never a simulated claim. Repo write is denied;
    there is no caller-selectable posture in R5.
    """

    repo_write: str = "denied"
    repo_read: str = "none"
    home_isolation: str = "isolated_home"
    os_enforcement: str = "declared_not_available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_write": self.repo_write,
            "repo_read": self.repo_read,
            "home_isolation": self.home_isolation,
            "os_enforcement": self.os_enforcement,
        }


@dataclass(frozen=True)
class OneShotCliRunResult:
    status: str
    machine_error_code: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    timed_out: bool
    cancelled: bool
    duration_seconds: float
    pid: int | None
    resume_supported: bool = False
    resume_reason: str = ONE_SHOT_NO_RESUME_REASON

    def to_dict(self) -> dict[str, Any]:
        safe_stdout = _redact_one_shot_text(self.stdout)
        safe_stderr = _redact_one_shot_text(self.stderr)
        raw = {
            "status": self.status,
            "machine_error_code": self.machine_error_code,
            "exit_code": self.exit_code,
            "stdout": safe_stdout,
            "stderr": safe_stderr,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "duration_seconds": self.duration_seconds,
            "pid": self.pid,
            "resume_supported": self.resume_supported,
            "resume_reason": self.resume_reason,
        }
        redacted = command_packets.redact_command_packet_value(raw)
        redacted["output_redacted"] = (
            safe_stdout != self.stdout or safe_stderr != self.stderr
        )
        return redacted


# Immutable production declarations. R61/R62 admit the Qwen and Kimi adapter
# contracts but do not grant binary, auth, or live-provider authority.
SERVER_OWNED_TOOL_MANIFEST: tuple[OneShotToolManifestEntry, ...] = (
    OneShotToolManifestEntry(
        tool_id="qwen-cli",
        provider_id="qwen",
        binary_name="qwen",
        display_name="Qwen Code CLI",
        version_args=("--version",),
        output_profiles=("text", "json"),
        allowed_argv_schema=QWEN_ALLOWED_ARGV_SCHEMA,
        operational_args=QWEN_OPERATIONAL_ARGS,
        allowed_environment_keys=(
            "QWEN_HOME",
            "QWEN_RUNTIME_DIR",
            "QWEN_PROJECT_ROOT",
            *QWEN_FIXED_ENV,
        ),
        output_parser="json_document_or_text",
        sandbox_policy=QWEN_SANDBOX_POLICY,
        auth_strategy=QWEN_AUTH_STRATEGY,
        network_policy=QWEN_NETWORK_POLICY,
        provider_adapter_admitted=True,
    ),
    OneShotToolManifestEntry(
        tool_id="kimi-cli",
        provider_id="kimi",
        binary_name="kimi",
        display_name="Kimi Code CLI",
        version_args=("--version",),
        output_profiles=("text", "json_lines"),
        allowed_argv_schema=KIMI_ALLOWED_ARGV_SCHEMA,
        operational_args=KIMI_OPERATIONAL_ARGS,
        allowed_environment_keys=(
            "KIMI_CODE_HOME",
            "KIMI_SNAPSHOT_ROOT",
            *KIMI_FIXED_ENV,
        ),
        output_parser="json_lines",
        sandbox_policy=KIMI_SANDBOX_POLICY,
        auth_strategy=KIMI_AUTH_STRATEGY,
        network_policy=KIMI_NETWORK_POLICY,
        provider_adapter_admitted=True,
    ),
)

_ADMISSION_RECORD_KEYS = frozenset(
    {
        "tool_id",
        "provider_id",
        "manifest_sha256",
        "binary_realpath",
        "binary_sha256",
        "binary_uid",
        "binary_mode",
        "bundle_root_realpath",
        "bundle_sha256",
        "bundle_file_count",
        "bundle_total_bytes",
        "version_text",
        "observed_at_utc",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class AdmissionStoreRead:
    records: Mapping[str, Mapping[str, Any]]
    machine_error_code: str
    reason: str

    @property
    def ok(self) -> bool:
        return self.machine_error_code == ONE_SHOT_OK


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def manifest_entry_digest(entry: OneShotToolManifestEntry) -> str:
    """Digest the complete immutable declaration for one tool."""
    return hashlib.sha256(_canonical_json_bytes(entry.to_dict())).hexdigest()


def _declaration_invalid_reason(entry: OneShotToolManifestEntry) -> str | None:
    identifier = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    if not entry.server_owned:
        return "declaration_not_server_owned"
    if not identifier.fullmatch(entry.tool_id) or not identifier.fullmatch(
        entry.provider_id
    ):
        return "declaration_identifier_invalid"
    binary_name = str(entry.binary_name or "")
    if not binary_name or "\x00" in binary_name or not entry.version_args:
        return "declaration_binary_or_version_probe_invalid"
    if _contains_secret_shape(entry.version_args, entry.operational_args):
        return "declaration_contains_secret_shaped_argv"
    if not entry.allowed_argv_schema:
        return "declaration_argv_schema_missing"
    if any(key not in PROVIDER_ENV_VARS for key in entry.allowed_environment_keys):
        return "declaration_environment_key_not_allowlisted"
    if entry.cwd_policy != "sealed_sandbox_cwd":
        return "declaration_cwd_policy_invalid"
    if entry.output_parser not in {
        "auto",
        "text",
        "key_value",
        "json_lines",
        "json_lines_or_text",
        "json_document_or_text",
    }:
        return "declaration_output_parser_invalid"
    if not set(entry.output_profiles).issubset(
        {"text", "key_value", "json", "json_lines"}
    ):
        return "declaration_output_profile_invalid"
    if (
        isinstance(entry.timeout_seconds, bool)
        or not isinstance(entry.timeout_seconds, (int, float))
        or not 0 < entry.timeout_seconds <= DEFAULT_RUN_TIMEOUT_SECONDS
    ):
        return "declaration_timeout_invalid"
    if (
        isinstance(entry.output_cap_bytes, bool)
        or not isinstance(entry.output_cap_bytes, int)
        or not 0 < entry.output_cap_bytes <= DEFAULT_OUTPUT_CAP_BYTES
    ):
        return "declaration_output_cap_invalid"
    if entry.process_group_policy != "new_session_group_termination":
        return "declaration_process_group_policy_invalid"
    if entry.sandbox_policy not in {
        "deny_default_offline",
        QWEN_SANDBOX_POLICY,
    }:
        return "declaration_sandbox_policy_invalid"
    if entry.session_policy != ONE_SHOT_NO_RESUME_REASON:
        return "declaration_session_policy_invalid"
    if not entry.auth_strategy:
        return "declaration_auth_strategy_invalid"
    if (
        entry.network_policy not in {"denied", QWEN_NETWORK_POLICY}
        and not entry.network_policy.startswith("denied_pending_")
    ):
        return "declaration_network_policy_invalid"
    return None


def _contains_secret_shape(*values: Any) -> bool:
    if command_packets.command_packet_has_secret_leak(
        {"one_shot_input": list(values)}
    ):
        return True
    return any(_redact_one_shot_text(value) != str(value or "") for value in values)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _trusted_realpath_root(path: Path) -> Path | None:
    roots = sorted(
        (Path(item).resolve(strict=False) for item in TRUSTED_BINARY_REALPATH_ROOTS),
        key=lambda item: len(str(item)),
        reverse=True,
    )
    for root in roots:
        if _path_is_within(path, root):
            return root
    return None


def _validate_server_owned_binary(path: Path | str) -> tuple[str | None, str]:
    """Validate one exact executable against fixed roots and owner/mode policy."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return None, "binary_path_not_absolute"
    try:
        resolved = candidate.resolve(strict=True)
        info = resolved.stat()
    except OSError:
        return None, "binary_missing"
    if not stat.S_ISREG(info.st_mode) or not os.access(resolved, os.X_OK):
        return None, "binary_not_executable_regular_file"
    trusted_root = _trusted_realpath_root(resolved)
    if trusted_root is None:
        return None, "binary_realpath_outside_trusted_roots"
    allowed_owners = {0, os.getuid()}
    current = resolved
    while True:
        try:
            current_info = current.stat()
        except OSError:
            return None, "binary_path_component_unreadable"
        if current_info.st_uid not in allowed_owners:
            return None, "binary_owner_unsafe"
        if stat.S_IMODE(current_info.st_mode) & 0o022:
            return None, "binary_mode_unsafe"
        if current == trusted_root:
            break
        parent = current.parent
        if parent == current or not _path_is_within(parent, trusted_root):
            return None, "binary_realpath_root_mismatch"
        current = parent
    return str(resolved), "ok"


def _validate_admission_record(tool_id: str, value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _ADMISSION_RECORD_KEYS:
        return False
    string_fields = _ADMISSION_RECORD_KEYS - {
        "binary_uid",
        "bundle_file_count",
        "bundle_total_bytes",
    }
    if any(not isinstance(value.get(field), str) for field in string_fields):
        return False
    if value.get("tool_id") != tool_id or not tool_id:
        return False
    if not isinstance(value.get("binary_uid"), int) or value["binary_uid"] < 0:
        return False
    if not _SHA256_RE.fullmatch(value.get("manifest_sha256", "")):
        return False
    if not _SHA256_RE.fullmatch(value.get("binary_sha256", "")):
        return False
    realpath = value.get("binary_realpath", "")
    if not realpath.startswith(os.path.sep) or os.path.realpath(realpath) != realpath:
        return False
    if not re.fullmatch(r"0o[0-7]{3,4}", value.get("binary_mode", "")):
        return False
    bundle_root = value.get("bundle_root_realpath", "")
    bundle_digest = value.get("bundle_sha256", "")
    bundle_file_count = value.get("bundle_file_count")
    bundle_total_bytes = value.get("bundle_total_bytes")
    if not isinstance(bundle_file_count, int) or isinstance(bundle_file_count, bool):
        return False
    if not isinstance(bundle_total_bytes, int) or isinstance(bundle_total_bytes, bool):
        return False
    if bundle_file_count < 0 or bundle_total_bytes < 0:
        return False
    if bundle_root:
        if (
            not bundle_root.startswith(os.path.sep)
            or os.path.realpath(bundle_root) != bundle_root
            or not _SHA256_RE.fullmatch(bundle_digest)
            or bundle_file_count <= 0
        ):
            return False
    elif bundle_digest or bundle_file_count or bundle_total_bytes:
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value["provider_id"]):
        return False
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value["observed_at_utc"]
    ):
        return False
    if not value["version_text"] or len(value["version_text"].encode("utf-8")) > 4096:
        return False
    if _contains_secret_shape(value["version_text"]):
        return False
    return True


def _managed_bundle_root(
    binary_path: Path | str,
    *,
    bundle_roots: Sequence[Path | str],
) -> Path | None:
    """Return the first-level immutable package containing a binary.

    Only code-owned bundle roots are considered. A package is exactly one
    child beneath such a root, preventing a probe from widening read access to
    the complete admission store or to an ambient package-manager prefix.
    """
    binary = Path(binary_path).resolve(strict=False)
    for raw_root in bundle_roots:
        root = Path(raw_root).resolve(strict=False)
        try:
            relative = binary.relative_to(root)
        except ValueError:
            continue
        if len(relative.parts) < 2:
            continue
        package = (root / relative.parts[0]).resolve(strict=False)
        try:
            package.relative_to(root)
        except ValueError:
            continue
        if package.is_dir():
            return package
    return None


def compute_bundle_digest(
    root: Path | str,
    *,
    size_limit: int = DEFAULT_BUNDLE_DIGEST_SIZE_LIMIT,
    file_count_limit: int = DEFAULT_BUNDLE_FILE_COUNT_LIMIT,
) -> tuple[str, int, int]:
    """Hash one safe immutable CLI bundle without following symlink escapes."""
    bundle = Path(root).resolve(strict=True)
    root_info = bundle.lstat()
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or root_info.st_uid not in {0, os.getuid()}
        or stat.S_IMODE(root_info.st_mode) & 0o022
    ):
        raise ValueError("bundle_root_owner_or_mode_unsafe")

    records: list[dict[str, Any]] = []
    file_count = 0
    total_bytes = 0
    for current_raw, dirs, files in os.walk(bundle, topdown=True, followlinks=False):
        current = Path(current_raw)
        names = sorted([*dirs, *files])
        dirs[:] = sorted(dirs)
        for name in names:
            path = current / name
            info = path.lstat()
            relative = path.relative_to(bundle).as_posix()
            mode = stat.S_IMODE(info.st_mode)
            if info.st_uid not in {0, os.getuid()} or mode & 0o022:
                raise ValueError("bundle_entry_owner_or_mode_unsafe")
            if stat.S_ISDIR(info.st_mode):
                records.append({"path": relative, "kind": "directory", "mode": mode})
                continue
            file_count += 1
            if file_count > file_count_limit:
                raise ValueError("bundle_file_count_limit_exceeded")
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                resolved_target = (path.parent / target).resolve(strict=True)
                try:
                    resolved_target.relative_to(bundle)
                except ValueError as exc:
                    raise ValueError("bundle_symlink_escape") from exc
                records.append(
                    {"path": relative, "kind": "symlink", "mode": mode, "target": target}
                )
                continue
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("bundle_special_file_not_admitted")
            total_bytes += info.st_size
            if total_bytes > size_limit:
                raise ValueError("bundle_size_limit_exceeded")
            records.append(
                {
                    "path": relative,
                    "kind": "file",
                    "mode": mode,
                    "size": info.st_size,
                    "sha256": compute_tool_digest(path, size_limit=size_limit),
                }
            )
    digest = hashlib.sha256(_canonical_json_bytes(records)).hexdigest()
    return digest, file_count, total_bytes


def _owned_path_is_safe(path: Path, *, expected_mode: int, directory: bool) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    return (
        expected_kind(info.st_mode)
        and not stat.S_ISLNK(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == expected_mode
    )


def _read_admission_store(root: Path | str) -> AdmissionStoreRead:
    root_path = Path(root)
    if not os.path.lexists(root_path):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_MISSING, "store_absent")
    if not _owned_path_is_safe(root_path, expected_mode=0o700, directory=True):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "store_mode_or_owner")
    lock_path = root_path / ADMISSION_LOCK_FILENAME
    if os.path.lexists(lock_path) and not _owned_path_is_safe(
        lock_path, expected_mode=0o600, directory=False
    ):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "lock_mode_or_owner")
    admission_path = root_path / ADMISSION_FILENAME
    if not os.path.lexists(admission_path):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_MISSING, "file_absent")
    if not _owned_path_is_safe(admission_path, expected_mode=0o600, directory=False):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "file_mode_or_owner")
    try:
        raw = admission_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "file_unreadable")
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "records"}:
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "schema_shape")
    if payload.get("schema_version") != ONE_SHOT_ADMISSION_SCHEMA_VERSION:
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "schema_version")
    records = payload.get("records")
    if not isinstance(records, dict) or any(
        not isinstance(tool_id, str) or not _validate_admission_record(tool_id, value)
        for tool_id, value in records.items()
    ):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "record_shape")
    if raw != _canonical_json_bytes(payload):
        return AdmissionStoreRead({}, CLI_BINARY_ADMISSION_INVALID, "noncanonical_json")
    return AdmissionStoreRead(records, ONE_SHOT_OK, "ok")


def _write_admission_record(
    root: Path | str,
    record: Mapping[str, Any],
) -> tuple[bool, str, str, list[str]]:
    """Atomically replace the canonical store while holding its real lock."""
    root_path = Path(root)
    changed: list[str] = []
    try:
        if not os.path.lexists(root_path):
            root_path.mkdir(parents=True, mode=0o700)
            os.chmod(root_path, 0o700)
            changed.append(str(root_path))
    except OSError:
        return False, CLI_BINARY_ADMISSION_INVALID, "store_create_failed", changed
    if not _owned_path_is_safe(root_path, expected_mode=0o700, directory=True):
        return False, CLI_BINARY_ADMISSION_INVALID, "store_mode_or_owner", changed

    lock_path = root_path / ADMISSION_LOCK_FILENAME
    lock_existed = os.path.lexists(lock_path)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    lock_fd: int | None = None
    temp_path: str | None = None
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
        lock_info = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.getuid()
            or stat.S_IMODE(lock_info.st_mode) != 0o600
        ):
            return False, CLI_BINARY_ADMISSION_INVALID, "lock_mode_or_owner", changed
        if not lock_existed:
            changed.append(str(lock_path))
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        current = _read_admission_store(root_path)
        if not current.ok and current.machine_error_code != CLI_BINARY_ADMISSION_MISSING:
            return False, current.machine_error_code, current.reason, changed
        records = dict(current.records)
        tool_id = str(record.get("tool_id", ""))
        if not _validate_admission_record(tool_id, dict(record)):
            return False, CLI_BINARY_ADMISSION_INVALID, "record_shape", changed
        records[tool_id] = dict(record)
        payload = {
            "schema_version": ONE_SHOT_ADMISSION_SCHEMA_VERSION,
            "records": dict(sorted(records.items())),
        }
        temp_fd, temp_path = tempfile.mkstemp(prefix=".admissions-", dir=root_path)
        try:
            os.fchmod(temp_fd, 0o600)
            with os.fdopen(temp_fd, "wb") as handle:
                handle.write(_canonical_json_bytes(payload))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, root_path / ADMISSION_FILENAME)
            temp_path = None
            directory_fd = os.open(root_path, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            return False, CLI_BINARY_ADMISSION_INVALID, "atomic_write_failed", changed
        admission_path = root_path / ADMISSION_FILENAME
        if str(admission_path) not in changed:
            changed.append(str(admission_path))
        return True, ONE_SHOT_OK, "ok", changed
    except OSError:
        return False, CLI_BINARY_ADMISSION_INVALID, "lock_or_write_failed", changed
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)


# Environment keys that must NEVER cross into a one-shot child. These are
# host/Codex/proxy surfaces unrelated to the sterile probe.
FORBIDDEN_ENV_KEYS = frozenset({
    "CODEX_HOME",
    "WBP_PROFILE_DIR",
    "SSH_AUTH_SOCK",
    "SSH_AGENT_PID",
    "ALL_PROXY", "all_proxy",
    "HTTP_PROXY", "http_proxy",
    "HTTPS_PROXY", "https_proxy",
    "NO_PROXY", "no_proxy",
    "GNOME_KEYRING_CONTROL",
    "KEYCHAIN",
    "BROWSER",
    "VISUAL", "EDITOR",
})


def is_sensitive_env_key(name: str) -> bool:
    upper = name.upper()
    return any(upper.endswith(suffix) for suffix in SECRET_ENV_SUFFIXES)


def is_forbidden_env_key(name: str) -> bool:
    """Host/Codex/proxy keys that must be scrubbed even if not secret-pattern."""
    return name in FORBIDDEN_ENV_KEYS or name.upper() in FORBIDDEN_ENV_KEYS


# Strict allowlist: only these ambient variables may cross into a one-shot
# child (PATH and HOME are always overridden by the runtime).
STERILE_ENV_ALLOWLIST = frozenset({
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP",
    "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES",
    "TERM", "SHELL",
    "SystemRoot", "WINDIR",  # Windows compat (harmless on macOS)
})

# Provider-specific home/runtime variables. They never enter from the
# ambient environment; they cross only as an explicit `provider_env`
# mapping validated by `OneShotRuntime`.
PROVIDER_PATH_ENV_VARS = frozenset({
    "QWEN_HOME", "QWEN_RUNTIME_DIR",
    "KIMI_CODE_HOME",
    "QWEN_PROJECT_ROOT", "KIMI_SNAPSHOT_ROOT",
})
PROVIDER_LITERAL_ENV_VALUES: Mapping[str, frozenset[str]] = MappingProxyType({
    key: frozenset({value})
    for key, value in {**QWEN_FIXED_ENV, **KIMI_FIXED_ENV}.items()
})
PROVIDER_ENV_VARS = PROVIDER_PATH_ENV_VARS | frozenset(PROVIDER_LITERAL_ENV_VALUES)


def build_sterile_environment(
    *,
    provider_home: Path | str | None = None,
    provider_env: Mapping[str, str] | None = None,
    keep: Sequence[str] = (),
    path_entries: Sequence[Path | str] = STERILE_PATH_ENTRIES,
) -> dict[str, str]:
    """Strict allowlist environment for one-shot children.

    Only explicitly-allowed ambient variables cross the boundary, PATH is
    pinned to the sterile entries, and HOME is NEVER inherited from the
    ambient environment: it is set only from the sealed provider home (the
    runtime substitutes the per-run sandbox cwd when no provider home is
    given). Provider variables come only from the validated `provider_env`
    mapping — never from the ambient environment.
    """
    allow = STERILE_ENV_ALLOWLIST | frozenset(keep)
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in allow and key not in ("PATH", "HOME"):
            env[key] = value
    env["PATH"] = os.pathsep.join(str(item) for item in path_entries)
    if provider_home is not None:
        env["HOME"] = str(Path(provider_home).resolve())
    for key, value in (provider_env or {}).items():
        env[str(key)] = str(value)
    return env


def env_digest(mapping: Mapping[str, str]) -> str:
    """Content-only digest of the prepared child environment."""
    canonical = json.dumps(
        dict(sorted(mapping.items())), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def compute_tool_digest(path: str, *, size_limit: int = DEFAULT_DIGEST_SIZE_LIMIT) -> str:
    """Exact sha256 of a size-bounded tool binary."""
    if os.stat(path).st_size > size_limit:
        raise OSError("tool binary exceeds the admission digest bound")
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def probe_os_sandbox() -> dict[str, Any]:
    """Honest OS-level sandbox availability probe (never simulated)."""
    available = shutil.which("sandbox-exec") is not None
    return {
        "os_sandbox_available": available,
        "os_enforcement": "os_sandbox_available" if available else "declared_not_available",
    }


def default_sandbox_profile() -> SandboxProfile:
    """The runtime default: denied repo write, probed OS enforcement."""
    return SandboxProfile(os_enforcement=probe_os_sandbox()["os_enforcement"])


# Seatbelt system read surface required for process startup on macOS.
# Empirically localized in R52: process startup aborts unless the root
# directory itself is readable (`literal "/"`); every allow path embedded
# in a profile must be realpath-resolved because seatbelt matches the
# kernel-resolved path string.
_SANDBOX_SYSTEM_READ_SUBPATHS = (
    "/usr",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/dev",
    "/private/var/db",
    # `/bin/sh` resolves through this sealed macOS selector path.
    "/private/var/select",
    "/private/etc",
    "/etc",
)


def build_server_owned_sandbox_profile(
    *,
    home_dir: Path | str,
    sandbox_cwd: Path | str,
    binary_path: Path | str | None = None,
    read_only_roots: Sequence[Path | str] = (),
    allow_provider_network: bool = False,
) -> str:
    """THE single production seatbelt profile builder (R52).

    Primary defense is `(deny default)` — never a private-path deny list.
    Allow surface:

    - process operations (required for startup on this OS version);
    - read of `/` itself (required by dyld path resolution);
    - read/exec of the immutable system runtime surface;
    - read+exec of the exact resolved binary being launched;
    - read/exec of a code-derived, admission-bound CLI bundle root when the
      launcher belongs to a managed standalone release;
    - read-only access to explicitly admitted read roots (for example an
      immutable snapshot root or a policy-admitted project root);
    - read+write of exactly the sealed provider home and the sandbox cwd
      (all paths realpath-resolved before embedding);
    - `/dev/null` and `/dev/dtracehelper` writes, posix shm.

    Network operations remain denied by default. Only an exact admitted
    operational provider child may request `allow_provider_network=True`;
    sterile probes never do so.
    """
    home_r = Path(home_dir).resolve()
    cwd_r = Path(sandbox_cwd).resolve()
    read_subpaths = " ".join(f'(subpath "{p}")' for p in _SANDBOX_SYSTEM_READ_SUBPATHS)
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        # Node's `os` module and PyInstaller's Python bootstrap both require
        # read-only kernel metadata during startup. This does not grant sysctl
        # writes and is shared by the two admitted standalone runtimes.
        "(allow sysctl-read)",
        '(allow file-read* (literal "/"))',
        f"(allow file-read* file-map-executable {read_subpaths})",
    ]
    if binary_path is not None:
        binary_r = Path(binary_path).resolve()
        lines.append(
            f'(allow file-read-data file-map-executable (literal "{binary_r}"))'
        )
    for root in read_only_roots:
        root_r = Path(root).resolve()
        ancestors = [
            parent
            for parent in reversed(root_r.parents)
            if str(parent) != os.path.sep
        ]
        if ancestors:
            ancestor_literals = " ".join(
                f'(literal "{parent}")' for parent in ancestors
            )
            lines.append(f"(allow file-read-metadata {ancestor_literals})")
        # Seatbelt's `subpath` does not grant metadata access to the root
        # object itself; both clauses are required for `cd bundle/bin/..` and
        # for single-file launchers that open their adjacent support tree.
        lines.append(
            f'(allow file-read* (literal "{root_r}") (subpath "{root_r}"))'
        )
    if allow_provider_network:
        lines.append("(allow network-outbound)")
    lines.extend(
        [
            f'(allow file-read* file-write* (subpath "{home_r}") (subpath "{cwd_r}"))',
            '(allow file-write* (literal "/dev/null") (literal "/dev/dtracehelper"))',
            "(allow ipc-posix-shm)",
        ]
    )
    return "\n".join(lines) + "\n"


# Provider env keys whose values double as admitted read-only roots in the
# sandbox profile. The policy layer (per-path admission) stays finer; the
# OS layer only widens read, never write.
_READ_ONLY_PROVIDER_ENV_KEYS = ("QWEN_PROJECT_ROOT", "KIMI_SNAPSHOT_ROOT")


def _resolve_binary(
    entry: OneShotToolManifestEntry,
    env: Mapping[str, str],
    *,
    search_roots: Sequence[Path | str] = STERILE_PATH_ENTRIES,
) -> str | None:
    binary = str(entry.binary_name).strip()
    if not binary:
        return None
    if os.path.sep in binary:
        if not entry.server_owned:
            resolved = Path(binary).resolve()
            if resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
        else:
            resolved, _reason = _validate_server_owned_binary(binary)
            if resolved is not None:
                return resolved
        return None
    if entry.server_owned:
        if Path(binary).name != binary or binary in {".", ".."}:
            return None
        for root in search_roots:
            candidate = Path(root) / binary
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                continue
            resolved, _reason = _validate_server_owned_binary(candidate)
            if resolved is not None:
                return resolved
        return None
    found = shutil.which(
        binary, path=env.get("PATH", os.pathsep.join(STERILE_PATH_ENTRIES))
    )
    return str(Path(found).resolve()) if found else None


def _read_capped(fh: Any, cap_bytes: int) -> tuple[str, bool]:
    fh.seek(0)
    data = fh.read(cap_bytes + 1)
    truncated = len(data) > cap_bytes
    return data[:cap_bytes].decode("utf-8", errors="replace"), truncated


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        return


def _process_group_exists(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The original child group is no longer signalable by its owner.
        # Treat it as outside this handle rather than risk a reused pgid.
        return False
    return True


def _wait_for_process_group_exit(
    pid: int,
    *,
    timeout_seconds: float = PROCESS_GROUP_EXIT_WAIT_SECONDS,
) -> bool:
    """Bound the post-signal race before reporting process-group cleanup."""
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while _process_group_exists(pid):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))
    return True


def _run_bounded(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    stdin_text: str | None,
    timeout_seconds: float,
    output_cap_bytes: int,
    cwd: Path | str | None = None,
) -> OneShotCliRunResult:
    """Bounded process-group run (timeout + cap; group kill on timeout)."""
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        stdin_file = None
        try:
            stdin = subprocess.DEVNULL
            if stdin_text is not None:
                stdin_file = tempfile.TemporaryFile()
                stdin_file.write(stdin_text.encode("utf-8"))
                stdin_file.seek(0)
                stdin = stdin_file
            process = subprocess.Popen(
                [str(item) for item in argv],
                stdin=stdin,
                stdout=stdout_file,
                stderr=stderr_file,
                env=dict(env),
                cwd=str(cwd) if cwd is not None else None,
                start_new_session=True,
                text=False,
                shell=False,
            )
        except FileNotFoundError:
            return OneShotCliRunResult(
                status="error",
                machine_error_code=TOOL_BINARY_NOT_FOUND,
                exit_code=None,
                stdout="",
                stderr="one-shot executable was not found.",
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                cancelled=False,
                duration_seconds=round(time.monotonic() - started, 3),
                pid=None,
            )
        except OSError:
            return OneShotCliRunResult(
                status="error",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                exit_code=None,
                stdout="",
                stderr="one-shot process could not be started.",
                stdout_truncated=False,
                stderr_truncated=False,
                timed_out=False,
                cancelled=False,
                duration_seconds=round(time.monotonic() - started, 3),
                pid=None,
            )
        finally:
            if stdin_file is not None:
                stdin_file.close()

        timed_out = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_group(process.pid)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

        if _process_group_exists(process.pid):
            _kill_process_group(process.pid)
            _wait_for_process_group_exit(process.pid)

        stdout, stdout_truncated = _read_capped(stdout_file, output_cap_bytes)
        stderr, stderr_truncated = _read_capped(stderr_file, output_cap_bytes)
        exit_code = process.returncode
        machine_error_code = (
            ONE_SHOT_RUN_TIMEOUT
            if timed_out
            else ONE_SHOT_OK
            if exit_code == 0
            else ONE_SHOT_RUN_FAILED
        )
        return OneShotCliRunResult(
            status="ok" if machine_error_code == ONE_SHOT_OK else "error",
            machine_error_code=machine_error_code,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            cancelled=False,
            duration_seconds=round(time.monotonic() - started, 3),
            pid=process.pid,
        )


class OneShotCliRunHandle:
    """Interactive handle for a running one-shot CLI.

    `cancel()` terminates the whole process group (SIGTERM, grace, SIGKILL);
    `wait()` collects the bounded result. One-shot runs never resume.
    """

    def __init__(
        self,
        process: subprocess.Popen,
        stdout_file: Any,
        stderr_file: Any,
        *,
        started: float,
        output_cap_bytes: int,
        env_digest_value: str,
        tool_id: str,
        sandbox_cwd: Path | None = None,
    ) -> None:
        self._process = process
        self._sandbox_cwd = sandbox_cwd
        self._stdout_file = stdout_file
        self._stderr_file = stderr_file
        self._started = started
        self._output_cap_bytes = output_cap_bytes
        self._env_digest = env_digest_value
        self.tool_id = tool_id
        self.pid = process.pid
        self.cancelled = False
        self._lock = threading.Lock()
        self._result: OneShotCliRunResult | None = None

    @property
    def env_digest(self) -> str:
        return self._env_digest

    def cancel(self, *, grace_seconds: float = CANCEL_GRACE_SECONDS) -> dict[str, Any]:
        """Terminate the whole process group; never just the leader."""
        if self._process.poll() is not None and not _process_group_exists(self.pid):
            return {"cancelled": False, "reason": "process_already_exited"}
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            return {"cancelled": False, "reason": "process_group_gone"}
        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            if not _process_group_exists(self.pid):
                break
            time.sleep(0.05)
        if _process_group_exists(self.pid):
            _kill_process_group(self.pid)
        try:
            self._process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass
        _wait_for_process_group_exit(self.pid)
        with self._lock:
            self.cancelled = True
        return {
            "cancelled": True,
            "pid": self.pid,
            "grace_seconds": grace_seconds,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        }

    def wait(self, timeout_seconds: float | None = None) -> OneShotCliRunResult:
        with self._lock:
            if self._result is not None:
                return self._result
        timed_out = False
        try:
            self._process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(self.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self._process.wait(timeout=CANCEL_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                _kill_process_group(self.pid)
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    pass
        if _process_group_exists(self.pid):
            _kill_process_group(self.pid)
            _wait_for_process_group_exit(self.pid)
        stdout, stdout_truncated = _read_capped(self._stdout_file, self._output_cap_bytes)
        stderr, stderr_truncated = _read_capped(self._stderr_file, self._output_cap_bytes)
        exit_code = self._process.returncode
        machine_error_code = (
            ONE_SHOT_CANCELLED
            if self.cancelled
            else ONE_SHOT_RUN_TIMEOUT
            if timed_out
            else ONE_SHOT_OK
            if exit_code == 0
            else ONE_SHOT_RUN_FAILED
        )
        result = OneShotCliRunResult(
            status="ok" if machine_error_code == ONE_SHOT_OK else "error",
            machine_error_code=machine_error_code,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timed_out=timed_out,
            cancelled=self.cancelled,
            duration_seconds=round(time.monotonic() - self._started, 3),
            pid=self.pid,
        )
        with self._lock:
            self._result = result
            self._stdout_file.close()
            self._stderr_file.close()
            if self._sandbox_cwd is not None:
                try:
                    os.chmod(self._sandbox_cwd, 0o755)
                    shutil.rmtree(self._sandbox_cwd, ignore_errors=True)
                except OSError:
                    pass
        return result


class OneShotRuntime:
    """Configured one-shot engine.

    Every instance carries its own sealed configuration. There is no
    module-level mutable state: no globals are read or written, no
    environment hooks exist, and nothing about an instance can be changed
    after construction. Tests build instances from `tests/fakes.py`;
    production surfaces use `ProductionOneShotFacade` instead.
    """

    def __init__(
        self,
        *,
        homes_root: Path | str,
        manifest: Sequence[OneShotToolManifestEntry] = (),
        bundle_roots: Sequence[Path | str] = (DEFAULT_BUNDLE_ROOT,),
        binary_search_roots: Sequence[Path | str] = STERILE_PATH_ENTRIES,
    ) -> None:
        root = Path(homes_root)
        self._homes_root = root
        self._manifest = tuple(manifest)
        self._bundle_roots = tuple(Path(item) for item in bundle_roots)
        self._binary_search_roots = tuple(str(item) for item in binary_search_roots)

    @property
    def homes_root(self) -> Path:
        return self._homes_root

    @property
    def manifest(self) -> tuple[OneShotToolManifestEntry, ...]:
        return self._manifest

    @property
    def bundle_roots(self) -> tuple[Path, ...]:
        return self._bundle_roots

    @property
    def binary_search_roots(self) -> tuple[str, ...]:
        return self._binary_search_roots

    def resolve_manifest_entry(self, tool_id: str) -> OneShotToolManifestEntry | None:
        """Resolve a tool id against this instance's manifest.

        Unknown ids fail closed (None)."""
        if not tool_id or not str(tool_id).strip():
            return None
        tool_id = str(tool_id).strip()
        for entry in self._manifest:
            if entry.tool_id == tool_id:
                return entry
        return None

    def _validate_provider_home(self, provider_home: Path | str | None) -> Path | None:
        """A provider home must resolve inside this instance's homes root."""
        if provider_home is None:
            return None
        resolved = Path(provider_home).resolve()
        try:
            resolved.relative_to(self._homes_root.resolve())
        except ValueError:
            raise RuntimeErrorInfo(
                "provider home must resolve inside the sealed homes root.",
                machine_error_code=ONE_SHOT_PATH_VIOLATION,
                operator_action="user_action",
            )
        return resolved

    def _validate_provider_env(
        self, provider_env: Mapping[str, str] | None
    ) -> dict[str, str]:
        """Provider env keys are allowlisted; values must be absolute paths.

        The sandbox profile — not the variable wording — enforces what the
        child may actually touch.
        """
        validated: dict[str, str] = {}
        for key, value in (provider_env or {}).items():
            key = str(key)
            if key not in PROVIDER_ENV_VARS:
                raise RuntimeErrorInfo(
                    f"provider env key '{key}' is not allowlisted.",
                    machine_error_code=ONE_SHOT_ENV_VIOLATION,
                    operator_action="user_action",
                )
            value = str(value)
            if key in PROVIDER_LITERAL_ENV_VALUES:
                if value not in PROVIDER_LITERAL_ENV_VALUES[key]:
                    raise RuntimeErrorInfo(
                        f"provider env value for '{key}' is not admitted.",
                        machine_error_code=ONE_SHOT_ENV_VIOLATION,
                        operator_action="user_action",
                    )
                validated[key] = value
                continue
            if not value.startswith(os.path.sep):
                raise RuntimeErrorInfo(
                    f"provider env value for '{key}' must be an absolute path.",
                    machine_error_code=ONE_SHOT_ENV_VIOLATION,
                    operator_action="user_action",
                )
            # Canonicalize: seatbelt matches the kernel-resolved path, so
            # symlinked prefixes (/var -> /private/var) must be resolved
            # before the value reaches the child or the sandbox profile.
            validated[key] = os.path.realpath(value)
        return validated

    def _prepare_child_env(
        self,
        *,
        provider_home: Path | str | None,
        provider_env: Mapping[str, str] | None,
    ) -> dict[str, str]:
        home = self._validate_provider_home(provider_home)
        extra = self._validate_provider_env(provider_env)
        return build_sterile_environment(
            provider_home=home,
            provider_env=extra,
            path_entries=self._binary_search_roots,
        )

    def create_provider_home(self, provider_id: str) -> dict[str, Any]:
        """Create an isolated provider home (0700) with a distinct runtime dir.

        The homes root is instance-sealed; there is no per-call override.
        Packet never contains secret values.
        """
        provider_id = str(provider_id or "").strip()
        if not provider_id or re.search(r"[^A-Za-z0-9_-]", provider_id):
            return build_command_payload(
                ok=False,
                human_message="provider id is invalid for one-shot home creation.",
                machine_error_code=ONE_SHOT_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "provider_id": provider_id,
                    "resume_supported": False,
                    "resume_reason": ONE_SHOT_NO_RESUME_REASON,
                },
            )
        root = self._homes_root
        home = root / provider_id
        runtime_dir = home / "runtime"
        skills_dir = home / KIMI_SKILLS_DIRNAME
        credentials_dir = home / KIMI_CREDENTIALS_DIRNAME
        created = False
        changed: list[str] = []
        try:
            if not home.exists():
                home.mkdir(parents=True, exist_ok=True)
                created = True
                changed.append(str(home))
            os.chmod(home, 0o700)
            if not runtime_dir.exists():
                runtime_dir.mkdir(parents=True, exist_ok=True)
                changed.append(str(runtime_dir))
            os.chmod(runtime_dir, 0o700)
            if provider_id == "kimi":
                if not skills_dir.exists():
                    skills_dir.mkdir(parents=True, exist_ok=True)
                    changed.append(str(skills_dir))
                os.chmod(skills_dir, 0o700)
                if not credentials_dir.exists():
                    credentials_dir.mkdir(parents=True, exist_ok=True)
                    changed.append(str(credentials_dir))
                os.chmod(credentials_dir, 0o700)
        except OSError:
            return build_command_payload(
                ok=False,
                human_message="provider home creation failed.",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=changed,
                exit_code=1,
                extra={
                    "provider_id": provider_id,
                    "created": created,
                    "resume_supported": False,
                    "resume_reason": ONE_SHOT_NO_RESUME_REASON,
                },
            )
        return build_command_payload(
            ok=True,
            human_message=f"provider home ready for {provider_id}.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=changed,
            exit_code=0,
            extra={
                "provider_id": provider_id,
                "home_path": str(home),
                "runtime_dir": str(runtime_dir),
                "mode": "0700",
                "created": created,
                "homes_root": str(root),
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def run_sterile_probe(
        self,
        tool_id: str,
        *,
        provider_home: Path | str | None = None,
        timeout_seconds: float = DEFAULT_PROBE_TIMEOUT_SECONDS,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
    ) -> dict[str, Any]:
        """Version/help probe of a declared tool in a sterile environment.

        The probe child runs under the same deny-default sandbox profile as
        a full run. Returns realpath, bounded digest, version text, and the
        env digest.
        """
        entry = self.resolve_manifest_entry(tool_id)
        if entry is None:
            return build_command_payload(
                ok=False,
                human_message=f"unknown one-shot tool id '{tool_id}'.",
                machine_error_code=ONE_SHOT_TOOL_UNKNOWN,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "server_owned": True},
            )
        env = self._prepare_child_env(provider_home=provider_home, provider_env=None)
        realpath = _resolve_binary(
            entry,
            env,
            search_roots=self._binary_search_roots,
        )
        if realpath is None:
            return build_command_payload(
                ok=False,
                human_message=f"tool binary not found for '{tool_id}' in sterile PATH.",
                machine_error_code=TOOL_BINARY_NOT_FOUND,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "binary_name": entry.binary_name},
            )
        try:
            digest = compute_tool_digest(realpath)
        except OSError:
            digest = ""
            return build_command_payload(
                ok=False,
                human_message=f"tool digest failed for '{tool_id}'.",
                machine_error_code=ONE_SHOT_PROBE_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "realpath": realpath},
            )
        handle = self.one_shot_cli_handle(
            tool_id,
            args=tuple(entry.version_args),
            provider_home=provider_home,
            output_cap_bytes=output_cap_bytes,
        )
        if isinstance(handle, dict):
            return handle
        probe = handle.wait(timeout_seconds=timeout_seconds)
        ok = probe.machine_error_code == ONE_SHOT_OK and not probe.timed_out
        version_source = probe.stdout.strip() or probe.stderr.strip()
        version_text = (
            _redact_one_shot_text(version_source.splitlines()[0])
            if version_source
            else ""
        )
        return build_command_payload(
            ok=ok,
            human_message=(
                f"probe ok for '{tool_id}'." if ok else f"probe failed for '{tool_id}'."
            ),
            machine_error_code=probe.machine_error_code,
            liveness="healthy",
            severity="info" if ok else "error",
            operator_action="none" if ok else "user_action",
            changed_files=[],
            exit_code=probe.exit_code,
            extra={
                "tool_id": tool_id,
                "server_owned": entry.server_owned,
                "realpath": realpath,
                "binary_sha256": digest,
                "version_text": version_text,
                "env_digest": handle.env_digest,
                "sterile_path": list(self._binary_search_roots),
                "timeout_seconds": timeout_seconds,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def one_shot_cli_handle(
        self,
        tool_id: str,
        *,
        args: Sequence[str] = (),
        stdin_text: str | None = None,
        provider_home: Path | str | None = None,
        provider_env: Mapping[str, str] | None = None,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
        allow_provider_network: bool = False,
    ) -> OneShotCliRunHandle | dict[str, Any]:
        """Spawn a declared tool as a one-shot process group.

        The child environment and sandbox are built from instance-sealed
        configuration only: no caller-provided environment, no
        caller-provided sandbox posture, no caller-provided homes root.
        Every child runs under the deny-default seatbelt profile; without
        `sandbox-exec` the runtime fails closed (`CLI_UNAVAILABLE_UNSAFE`).
        """
        entry = self.resolve_manifest_entry(tool_id)
        if entry is None:
            return build_command_payload(
                ok=False,
                human_message=f"unknown one-shot tool id '{tool_id}'.",
                machine_error_code=ONE_SHOT_TOOL_UNKNOWN,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "server_owned": True},
            )
        if _contains_secret_shape(tuple(str(item) for item in args), stdin_text or ""):
            return build_command_payload(
                ok=False,
                human_message="one-shot input was blocked by the secret boundary.",
                machine_error_code=ONE_SHOT_SECRET_INPUT_BLOCKED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "tool_id": tool_id,
                    "input_blocked": True,
                    "secret_value_exposed": False,
                },
            )
        prepared_env = self._prepare_child_env(
            provider_home=provider_home, provider_env=provider_env
        )
        realpath = _resolve_binary(
            entry,
            prepared_env,
            search_roots=self._binary_search_roots,
        )
        if realpath is None:
            return build_command_payload(
                ok=False,
                human_message=f"tool binary not found for '{tool_id}'.",
                machine_error_code=TOOL_BINARY_NOT_FOUND,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "binary_name": entry.binary_name},
            )
        argv = [realpath, *(str(item) for item in args)]
        stdout_file = tempfile.TemporaryFile()
        stderr_file = tempfile.TemporaryFile()
        stdin_file = None
        sandbox_exec = shutil.which("sandbox-exec")
        sandbox_cwd = Path(tempfile.mkdtemp(prefix="wbp-sandbox-ro-")).resolve()
        if not sandbox_exec:
            # No sandbox-exec: fail closed. There is no unsandboxed lane.
            shutil.rmtree(sandbox_cwd, ignore_errors=True)
            stdout_file.close()
            stderr_file.close()
            return build_command_payload(
                ok=False,
                human_message=(
                    f"one-shot CLI '{tool_id}' is unsafe: sandbox-exec is "
                    f"required and is not available."
                ),
                machine_error_code=CLI_UNAVAILABLE_UNSAFE,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "tool_id": tool_id,
                    "sandbox": default_sandbox_profile().to_dict(),
                    "reason": "sandbox_exec_absent",
                },
            )
        # HOME is exactly the sealed provider home, or the per-run sandbox
        # cwd when no provider home was given. The ambient user HOME must
        # never become the writable root of a one-shot child.
        if provider_home is not None:
            child_home = Path(prepared_env["HOME"]).resolve()
        else:
            child_home = sandbox_cwd
            prepared_env["HOME"] = str(sandbox_cwd)
        read_only_roots = [
            prepared_env[key]
            for key in _READ_ONLY_PROVIDER_ENV_KEYS
            if key in prepared_env
        ]
        bundle_root = _managed_bundle_root(
            realpath,
            bundle_roots=self._bundle_roots,
        )
        if bundle_root is not None:
            read_only_roots.append(bundle_root)
        profile_text = build_server_owned_sandbox_profile(
            home_dir=child_home,
            sandbox_cwd=sandbox_cwd,
            binary_path=realpath,
            read_only_roots=read_only_roots,
            allow_provider_network=allow_provider_network,
        )
        sandbox_profile_path = sandbox_cwd / "sandbox.sb"
        sandbox_profile_path.write_text(profile_text, encoding="utf-8")
        run_argv = [
            str(Path(sandbox_exec).resolve()),
            "-f", str(sandbox_profile_path),
            *argv,
        ]
        try:
            stdin = subprocess.DEVNULL
            if stdin_text is not None:
                stdin_file = tempfile.TemporaryFile()
                stdin_file.write(stdin_text.encode("utf-8"))
                stdin_file.seek(0)
                stdin = stdin_file
            process = subprocess.Popen(
                run_argv,
                stdin=stdin,
                stdout=stdout_file,
                stderr=stderr_file,
                env=dict(prepared_env),
                cwd=str(sandbox_cwd),
                start_new_session=True,
                text=False,
                shell=False,
            )
        except OSError:
            stdout_file.close()
            stderr_file.close()
            if stdin_file is not None:
                stdin_file.close()
            shutil.rmtree(sandbox_cwd, ignore_errors=True)
            return build_command_payload(
                ok=False,
                human_message=f"one-shot spawn failed for '{tool_id}'.",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"tool_id": tool_id, "sandbox": default_sandbox_profile().to_dict()},
            )
        finally:
            if stdin_file is not None:
                stdin_file.close()
        return OneShotCliRunHandle(
            process,
            stdout_file,
            stderr_file,
            started=time.monotonic(),
            output_cap_bytes=output_cap_bytes,
            env_digest_value=env_digest(prepared_env),
            tool_id=tool_id,
            sandbox_cwd=sandbox_cwd,
        )

    def one_shot_cli_run(
        self,
        tool_id: str,
        *,
        args: Sequence[str] = (),
        stdin_text: str | None = None,
        provider_home: Path | str | None = None,
        provider_env: Mapping[str, str] | None = None,
        timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS,
        output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
        cancel_after_seconds: float | None = None,
        allow_provider_network: bool = False,
    ) -> dict[str, Any]:
        """Bounded one-shot run built from instance-sealed configuration."""
        handle = self.one_shot_cli_handle(
            tool_id,
            args=args,
            stdin_text=stdin_text,
            provider_home=provider_home,
            provider_env=provider_env,
            output_cap_bytes=output_cap_bytes,
            allow_provider_network=allow_provider_network,
        )
        if isinstance(handle, dict):
            return handle
        if cancel_after_seconds is not None:
            deadline = time.monotonic() + cancel_after_seconds
            while time.monotonic() < deadline:
                if handle._process.poll() is not None:
                    break
                time.sleep(0.05)
            if handle._process.poll() is None:
                handle.cancel()
        result = handle.wait(timeout_seconds=timeout_seconds)
        profile = default_sandbox_profile().to_dict()
        return build_command_payload(
            ok=result.status == "ok",
            human_message=(
                f"one-shot run '{tool_id}' finished." if result.status == "ok"
                else f"one-shot run '{tool_id}' failed."
            ),
            machine_error_code=result.machine_error_code,
            liveness="healthy",
            severity="info" if result.status == "ok" else "error",
            operator_action="none" if result.status == "ok" else "user_action",
            changed_files=[],
            exit_code=result.exit_code,
            extra={
                "tool_id": tool_id,
                "run": result.to_dict(),
                "sandbox": profile,
                "env_digest": handle.env_digest,
                "timeout_seconds": timeout_seconds,
                "provider_network_allowed": bool(allow_provider_network),
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def one_shot_auth_session(
        self,
        provider_id: str,
        provider_home: Path | str,
    ) -> dict[str, Any]:
        """Begin a presence-only auth session inside the provider home.

        The provider home must resolve inside this instance's homes root.
        The packet carries session presence and paths, never secret values.
        """
        provider_id = str(provider_id or "").strip()
        home = self._validate_provider_home(provider_home)
        assert home is not None
        auth_dir = home / "auth"
        session_id = uuid.uuid4().hex
        try:
            auth_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(auth_dir, 0o700)
            session_file = auth_dir / "session.json"
            payload = {
                "provider_id": provider_id,
                "session_id": session_id,
                "presence_only": True,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            session_file.write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
            os.chmod(session_file, 0o600)
        except OSError:
            return build_command_payload(
                ok=False,
                human_message="auth session start failed.",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"provider_id": provider_id, "session_id": session_id},
            )
        return build_command_payload(
            ok=True,
            human_message=f"auth session started for {provider_id} (presence-only).",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[str(auth_dir), str(session_file)],
            exit_code=0,
            extra={
                "provider_id": provider_id,
                "session_id": session_id,
                "auth_dir": str(auth_dir),
                "presence_only": True,
                "secret_values_exposed": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def one_shot_auth_status(self, provider_home: Path | str) -> dict[str, Any]:
        """Presence-only auth status for a provider home."""
        home = self._validate_provider_home(provider_home)
        assert home is not None
        session_file = home / "auth" / "session.json"
        present = session_file.is_file()
        return build_command_payload(
            ok=True,
            human_message="auth session present." if present else "no auth session.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "auth_present": present,
                "auth_dir": str(session_file.parent),
                "presence_only": True,
                "secret_values_exposed": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def end_one_shot_auth_session(self, provider_home: Path | str) -> dict[str, Any]:
        """End the auth session by removing its presence marker."""
        home = self._validate_provider_home(provider_home)
        assert home is not None
        session_file = home / "auth" / "session.json"
        changed: list[str] = []
        removed = False
        try:
            if session_file.is_file():
                session_file.unlink()
                removed = True
                changed.append(str(session_file))
        except OSError:
            return build_command_payload(
                ok=False,
                human_message="auth session end failed.",
                machine_error_code=ONE_SHOT_RUN_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=changed,
                exit_code=1,
                extra={"removed": removed},
            )
        return build_command_payload(
            ok=True,
            human_message="auth session ended." if removed else "no auth session to end.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=changed,
            exit_code=0,
            extra={
                "removed": removed,
                "presence_only": True,
                "secret_values_exposed": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )


class ProductionOneShotFacade:
    """Immutable production facade backed by exact binary admissions.

    The default singleton is sealed to code-owned constants. Explicitly
    constructed instances exist only so hermetic tests can use throwaway roots;
    they never mutate or enable the singleton. There is no ambient grant.
    """

    def __init__(
        self,
        *,
        homes_root: Path | str = DEFAULT_HOMES_ROOT,
        manifest: Sequence[OneShotToolManifestEntry] = SERVER_OWNED_TOOL_MANIFEST,
        admission_root: Path | str = DEFAULT_ADMISSION_ROOT,
    ) -> None:
        self._homes_root = Path(homes_root)
        self._manifest = tuple(manifest)
        self._admission_root = Path(admission_root)
        default_admission_bin = str(DEFAULT_ADMISSION_ROOT / "bin")
        self._binary_search_roots = tuple(
            item for item in STERILE_PATH_ENTRIES if item != default_admission_bin
        ) + (str(self._admission_root / "bin"),)
        self._runtime = OneShotRuntime(
            homes_root=self._homes_root,
            manifest=self._manifest,
            bundle_roots=(self._admission_root / "releases",),
            binary_search_roots=self._binary_search_roots,
        )

    @property
    def homes_root(self) -> Path:
        return self._homes_root

    @property
    def admission_root(self) -> Path:
        return self._admission_root

    def _blocked_packet(
        self,
        surface: str,
        machine_error_code: str,
        reason: str,
        *,
        changed_files: Sequence[str] = (),
        **extra: Any,
    ) -> dict[str, Any]:
        payload_extra = {
            "surface": surface,
            "cli_disabled": False,
            "cli_operational": False,
            "production_admission_supported": True,
            "blocked_reason": reason,
            "resume_supported": False,
            "resume_reason": ONE_SHOT_NO_RESUME_REASON,
        }
        payload_extra.update(extra)
        return build_command_payload(
            ok=False,
            human_message=f"one-shot CLI surface '{surface}' is blocked ({reason}).",
            machine_error_code=machine_error_code,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=list(changed_files),
            exit_code=1,
            extra=payload_extra,
        )

    def _entry_for_tool(self, tool_id: str) -> OneShotToolManifestEntry | None:
        tool_id = str(tool_id or "").strip()
        matches = [entry for entry in self._manifest if entry.tool_id == tool_id]
        return matches[0] if len(matches) == 1 else None

    def _entry_for_provider(self, provider_id: str) -> OneShotToolManifestEntry | None:
        provider_id = str(provider_id or "").strip()
        matches = [entry for entry in self._manifest if entry.provider_id == provider_id]
        return matches[0] if len(matches) == 1 else None

    def _unknown_packet(
        self, surface: str, *, tool_id: str = "", provider_id: str = ""
    ) -> dict[str, Any]:
        return self._blocked_packet(
            surface,
            ONE_SHOT_TOOL_UNKNOWN,
            "declaration_unknown_or_ambiguous",
            tool_id=tool_id,
            provider_id=provider_id,
        )

    def _adapter_block(
        self, surface: str, entry: OneShotToolManifestEntry
    ) -> dict[str, Any] | None:
        if entry.server_owned and entry.provider_adapter_admitted:
            return None
        return self._blocked_packet(
            surface,
            CLI_PROVIDER_ADAPTER_NOT_ADMITTED,
            "provider_adapter_not_admitted",
            tool_id=entry.tool_id,
            provider_id=entry.provider_id,
            provider_adapter_admitted=False,
        )

    def _declaration_block(
        self, surface: str, entry: OneShotToolManifestEntry
    ) -> dict[str, Any] | None:
        reason = _declaration_invalid_reason(entry)
        if reason is None:
            return None
        return self._blocked_packet(
            surface,
            ONE_SHOT_SCHEMA_INVALID,
            reason,
            tool_id=entry.tool_id,
            provider_id=entry.provider_id,
        )

    def _read_target_admission(
        self,
        surface: str,
        entry: OneShotToolManifestEntry,
        *,
        revalidate_version: bool = True,
    ) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None]:
        store = _read_admission_store(self._admission_root)
        if not store.ok:
            return None, self._blocked_packet(
                surface,
                store.machine_error_code,
                store.reason,
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                admission_root=str(self._admission_root),
            )
        record = store.records.get(entry.tool_id)
        if record is None:
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_ADMISSION_MISSING,
                "tool_record_absent",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        if record.get("provider_id") != entry.provider_id:
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_ADMISSION_INVALID,
                "provider_binding_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        declaration_digest = manifest_entry_digest(entry)
        if record.get("manifest_sha256") != declaration_digest:
            return None, self._blocked_packet(
                surface,
                CLI_ADMISSION_DIGEST_MISMATCH,
                "manifest_digest_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                manifest_sha256=declaration_digest,
            )

        env = build_sterile_environment(path_entries=self._binary_search_roots)
        current_realpath = _resolve_binary(
            entry,
            env,
            search_roots=self._binary_search_roots,
        )
        if current_realpath is None or current_realpath != record.get("binary_realpath"):
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_IDENTITY_DRIFT,
                "binary_realpath_missing_or_drifted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        validated_realpath, identity_reason = _validate_server_owned_binary(
            current_realpath
        )
        if validated_realpath is None:
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_IDENTITY_DRIFT,
                identity_reason,
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        try:
            binary_info = Path(validated_realpath).stat()
            current_digest = compute_tool_digest(validated_realpath)
        except OSError:
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_IDENTITY_DRIFT,
                "binary_identity_unreadable",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        if (
            current_digest != record.get("binary_sha256")
            or binary_info.st_uid != record.get("binary_uid")
            or oct(stat.S_IMODE(binary_info.st_mode)) != record.get("binary_mode")
        ):
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_IDENTITY_DRIFT,
                "binary_digest_owner_or_mode_drifted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )

        current_bundle_root = _managed_bundle_root(
            validated_realpath,
            bundle_roots=(self._admission_root / "releases",),
        )
        recorded_bundle_root = str(record.get("bundle_root_realpath") or "")
        if (str(current_bundle_root) if current_bundle_root is not None else "") != recorded_bundle_root:
            return None, self._blocked_packet(
                surface,
                CLI_BINARY_IDENTITY_DRIFT,
                "bundle_root_missing_or_drifted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        if current_bundle_root is not None:
            try:
                bundle_digest, bundle_file_count, bundle_total_bytes = compute_bundle_digest(
                    current_bundle_root
                )
            except (OSError, ValueError):
                return None, self._blocked_packet(
                    surface,
                    CLI_BINARY_IDENTITY_DRIFT,
                    "bundle_identity_unreadable_or_unsafe",
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                )
            if (
                bundle_digest != record.get("bundle_sha256")
                or bundle_file_count != record.get("bundle_file_count")
                or bundle_total_bytes != record.get("bundle_total_bytes")
            ):
                return None, self._blocked_packet(
                    surface,
                    CLI_BINARY_IDENTITY_DRIFT,
                    "bundle_digest_or_shape_drifted",
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                )

        if revalidate_version:
            probe = self._runtime.run_sterile_probe(
                entry.tool_id,
                timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS,
                output_cap_bytes=min(entry.output_cap_bytes, DEFAULT_OUTPUT_CAP_BYTES),
            )
            if (
                probe.get("status") != "ok"
                or probe.get("realpath") != record.get("binary_realpath")
                or probe.get("binary_sha256") != record.get("binary_sha256")
                or probe.get("version_text") != record.get("version_text")
            ):
                return None, self._blocked_packet(
                    surface,
                    CLI_BINARY_IDENTITY_DRIFT,
                    "version_revalidation_failed",
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                    probe_machine_error_code=probe.get("machine_error_code"),
                )
        return record, None

    def _ready_provider_entry(
        self, surface: str, provider_id: str
    ) -> tuple[OneShotToolManifestEntry | None, dict[str, Any] | None]:
        entry = self._entry_for_provider(provider_id)
        if entry is None:
            return None, self._unknown_packet(surface, provider_id=str(provider_id))
        blocked = self._declaration_block(surface, entry)
        if blocked is not None:
            return None, blocked
        blocked = self._adapter_block(surface, entry)
        if blocked is not None:
            return None, blocked
        _record, blocked = self._read_target_admission(surface, entry)
        if blocked is not None:
            return None, blocked
        return entry, None

    def _qwen_home_readiness(
        self,
        surface: str,
        entry: OneShotToolManifestEntry,
    ) -> tuple[dict[str, Path] | None, dict[str, Any] | None]:
        """Validate presence-only Qwen home/auth state without reading secrets."""
        home = self._homes_root / entry.provider_id
        runtime_dir = home / "runtime"
        auth_path = home / QWEN_AUTH_FILENAME
        if not _owned_path_is_safe(home, expected_mode=0o700, directory=True):
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_provider_home_missing_or_unsafe",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                secret_value_exposed=False,
            )
        if not _owned_path_is_safe(runtime_dir, expected_mode=0o700, directory=True):
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_runtime_dir_missing_or_unsafe",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                secret_value_exposed=False,
            )
        if not _owned_path_is_safe(auth_path, expected_mode=0o600, directory=False):
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_auth_config_missing_or_unsafe",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        try:
            auth_size = auth_path.stat().st_size
        except OSError:
            auth_size = 0
        if not 0 < auth_size <= DEFAULT_OUTPUT_CAP_BYTES:
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_auth_config_empty_or_oversized",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        return {
            "home": home.resolve(),
            "runtime_dir": runtime_dir.resolve(),
            "auth_path": auth_path.resolve(),
        }, None

    def _kimi_home_readiness(
        self,
        surface: str,
        entry: OneShotToolManifestEntry,
    ) -> tuple[dict[str, Path] | None, dict[str, Any] | None]:
        """Validate Kimi auth/config presence without reading its contents."""
        home = self._homes_root / entry.provider_id
        runtime_dir = home / "runtime"
        skills_dir = home / KIMI_SKILLS_DIRNAME
        credentials_dir = home / KIMI_CREDENTIALS_DIRNAME
        auth_path = home / KIMI_AUTH_FILENAME
        path_checks = (
            (home, "isolated_provider_home_missing_or_unsafe"),
            (runtime_dir, "isolated_runtime_dir_missing_or_unsafe"),
            (skills_dir, "isolated_skills_dir_missing_or_unsafe"),
            (credentials_dir, "isolated_credentials_dir_missing_or_unsafe"),
        )
        for path, reason in path_checks:
            if not _owned_path_is_safe(path, expected_mode=0o700, directory=True):
                return None, self._blocked_packet(
                    surface,
                    CLI_AUTH_NOT_ADMITTED,
                    reason,
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                    auth_present=False,
                    auth_presence_only=True,
                    secret_value_exposed=False,
                )
        try:
            skills_empty = next(skills_dir.iterdir(), None) is None
        except OSError:
            skills_empty = False
        if not skills_empty:
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_skills_dir_not_empty",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        if not _owned_path_is_safe(auth_path, expected_mode=0o600, directory=False):
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_auth_config_missing_or_unsafe",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        try:
            auth_size = auth_path.stat().st_size
        except OSError:
            auth_size = 0
        if not 0 < auth_size <= DEFAULT_OUTPUT_CAP_BYTES:
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_auth_config_empty_or_oversized",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        try:
            credential_files = list(credentials_dir.iterdir())
            credentials_safe = bool(credential_files) and all(
                path.suffix == ".json"
                and _owned_path_is_safe(path, expected_mode=0o600, directory=False)
                and 0 < path.stat().st_size <= DEFAULT_OUTPUT_CAP_BYTES
                for path in credential_files
            )
        except OSError:
            credentials_safe = False
        if not credentials_safe:
            return None, self._blocked_packet(
                surface,
                CLI_AUTH_NOT_ADMITTED,
                "isolated_provider_credentials_missing_or_unsafe",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_present=False,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        for forbidden_name in ("mcp.json", "AGENTS.md", "agents", "plugins"):
            if os.path.lexists(home / forbidden_name):
                return None, self._blocked_packet(
                    surface,
                    CLI_AUTH_NOT_ADMITTED,
                    "isolated_unadmitted_extension_surface_present",
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                    extension_surface=forbidden_name,
                    auth_present=False,
                    auth_presence_only=True,
                    secret_value_exposed=False,
                )
        return {
            "home": home.resolve(),
            "runtime_dir": runtime_dir.resolve(),
            "skills_dir": skills_dir.resolve(),
            "credentials_dir": credentials_dir.resolve(),
            "auth_path": auth_path.resolve(),
        }, None

    def create_home(self, provider_id: str) -> dict[str, Any]:
        entry, blocked = self._ready_provider_entry("create_home", provider_id)
        if blocked is not None:
            return blocked
        assert entry is not None
        packet = self._runtime.create_provider_home(entry.provider_id)
        packet["production_admission_revalidated"] = True
        packet["manifest_sha256"] = manifest_entry_digest(entry)
        return packet

    def session(self, provider_id: str) -> dict[str, Any]:
        entry, blocked = self._ready_provider_entry("session", provider_id)
        if blocked is not None:
            return blocked
        assert entry is not None
        if entry.auth_strategy == QWEN_AUTH_STRATEGY and entry.provider_id == "qwen":
            readiness, blocked = self._qwen_home_readiness("session", entry)
            if blocked is not None:
                return blocked
            assert readiness is not None
            return build_command_payload(
                ok=True,
                human_message="Qwen isolated one-shot session is ready.",
                machine_error_code=ONE_SHOT_OK,
                liveness="healthy",
                severity="info",
                operator_action="none",
                changed_files=[],
                exit_code=0,
                extra={
                    "surface": "session",
                    "tool_id": entry.tool_id,
                    "provider_id": entry.provider_id,
                    "qwen_home": str(readiness["home"]),
                    "qwen_runtime_dir": str(readiness["runtime_dir"]),
                    "auth_present": True,
                    "auth_presence_only": True,
                    "secret_value_exposed": False,
                    "repo_write_policy": "denied",
                    "production_admission_revalidated": True,
                    "manifest_sha256": manifest_entry_digest(entry),
                    "resume_supported": False,
                    "resume_reason": ONE_SHOT_NO_RESUME_REASON,
                },
            )
        if entry.auth_strategy == KIMI_AUTH_STRATEGY and entry.provider_id == "kimi":
            readiness, blocked = self._kimi_home_readiness("session", entry)
            if blocked is not None:
                return blocked
            assert readiness is not None
            return build_command_payload(
                ok=True,
                human_message="Kimi isolated one-shot session is ready.",
                machine_error_code=ONE_SHOT_OK,
                liveness="healthy",
                severity="info",
                operator_action="none",
                changed_files=[],
                exit_code=0,
                extra={
                    "surface": "session",
                    "tool_id": entry.tool_id,
                    "provider_id": entry.provider_id,
                    "kimi_code_home": str(readiness["home"]),
                    "kimi_runtime_dir": str(readiness["runtime_dir"]),
                    "kimi_skills_dir": str(readiness["skills_dir"]),
                    "auth_present": True,
                    "auth_presence_only": True,
                    "secret_value_exposed": False,
                    "repo_write_policy": "denied",
                    "production_admission_revalidated": True,
                    "manifest_sha256": manifest_entry_digest(entry),
                    "resume_supported": False,
                    "resume_reason": ONE_SHOT_NO_RESUME_REASON,
                },
            )
        if entry.auth_strategy != "none":
            return self._blocked_packet(
                "session",
                CLI_AUTH_NOT_ADMITTED,
                "interactive_login_not_admitted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
            )
        packet = self._runtime.create_provider_home(entry.provider_id)
        packet["production_admission_revalidated"] = True
        packet["auth_required"] = False
        packet["tool_id"] = entry.tool_id
        return packet

    def auth_session(self, provider_id: str) -> dict[str, Any]:
        entry, blocked = self._ready_provider_entry("auth_session", provider_id)
        if blocked is not None:
            return blocked
        assert entry is not None
        if entry.auth_strategy == QWEN_AUTH_STRATEGY and entry.provider_id == "qwen":
            return self._blocked_packet(
                "auth_session",
                CLI_AUTH_NOT_ADMITTED,
                "operator_managed_isolated_auth_required",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
                auth_filename=QWEN_AUTH_FILENAME,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        if entry.auth_strategy == KIMI_AUTH_STRATEGY and entry.provider_id == "kimi":
            return self._blocked_packet(
                "auth_session",
                CLI_AUTH_NOT_ADMITTED,
                "operator_managed_isolated_auth_required",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
                auth_filename=KIMI_AUTH_FILENAME,
                auth_presence_only=True,
                secret_value_exposed=False,
            )
        if entry.auth_strategy != "none":
            return self._blocked_packet(
                "auth_session",
                CLI_AUTH_NOT_ADMITTED,
                "interactive_login_not_admitted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
            )
        return build_command_payload(
            ok=True,
            human_message=f"no auth session is required for '{entry.provider_id}'.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "surface": "auth_session",
                "tool_id": entry.tool_id,
                "provider_id": entry.provider_id,
                "auth_required": False,
                "production_admission_revalidated": True,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def probe(self, tool_id: str) -> dict[str, Any]:
        entry = self._entry_for_tool(tool_id)
        if entry is None:
            return self._unknown_packet("probe", tool_id=str(tool_id))
        blocked = self._declaration_block("probe", entry)
        if blocked is not None:
            return blocked
        packet = self._runtime.run_sterile_probe(
            entry.tool_id,
            timeout_seconds=DEFAULT_PROBE_TIMEOUT_SECONDS,
            output_cap_bytes=min(entry.output_cap_bytes, DEFAULT_OUTPUT_CAP_BYTES),
        )
        packet["provider_id"] = entry.provider_id
        packet["manifest_sha256"] = manifest_entry_digest(entry)
        packet["probe_grants_operational_authority"] = False
        return packet

    def _run_kimi_prompt(
        self,
        entry: OneShotToolManifestEntry,
        prompt: str,
        *,
        active_project_root: Path | str | None,
    ) -> dict[str, Any]:
        if (
            entry.allowed_argv_schema != KIMI_ALLOWED_ARGV_SCHEMA
            or entry.operational_args != KIMI_OPERATIONAL_ARGS
        ):
            return self._blocked_packet(
                "run_prompt",
                ONE_SHOT_SCHEMA_INVALID,
                "kimi_prompt_argv_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        if (
            entry.network_policy != KIMI_NETWORK_POLICY
            or entry.sandbox_policy != KIMI_SANDBOX_POLICY
        ):
            return self._blocked_packet(
                "run_prompt",
                CLI_NETWORK_POLICY_NOT_ADMITTED,
                "kimi_provider_network_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                network_policy=entry.network_policy,
                sandbox_policy=entry.sandbox_policy,
            )
        if entry.auth_strategy != KIMI_AUTH_STRATEGY:
            return self._blocked_packet(
                "run_prompt",
                CLI_AUTH_NOT_ADMITTED,
                "kimi_auth_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
            )
        record, blocked = self._read_target_admission("run_prompt", entry)
        if blocked is not None:
            return blocked
        assert record is not None
        readiness, blocked = self._kimi_home_readiness("run_prompt", entry)
        if blocked is not None:
            return blocked
        assert readiness is not None

        selected_root: Path | None = None
        root_fields: dict[str, Any] = {
            "active_project_root_required": False,
            "active_project_root_available": False,
            "active_project_root_source": "not_requested",
            "active_project_root_status": "not_requested",
            "active_project_root_path_recorded": False,
            "active_project_root_sha256": "",
            "active_project_root_is_wbp_repo": False,
            "active_project_root_git_available": False,
            "active_project_root_fallback_used": False,
            "active_project_root_legacy_target_repo_alias_used": False,
        }
        if active_project_root is not None:
            selected_root, root_fields = active_root.active_project_root_metadata(
                active_project_root,
                source="production_one_shot_prompt",
                wbp_repo_root=Path(__file__).resolve().parents[1],
                required=True,
            )
            if selected_root is None:
                return self._blocked_packet(
                    "run_prompt",
                    ONE_SHOT_PATH_VIOLATION,
                    str(root_fields["active_project_root_status"]),
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                    **root_fields,
                )

        provider_env = {
            "KIMI_CODE_HOME": str(readiness["home"]),
            **KIMI_FIXED_ENV,
        }
        args = (
            "--prompt",
            prompt,
            *KIMI_OPERATIONAL_ARGS,
            "--skills-dir",
            str(readiness["skills_dir"]),
        )
        if selected_root is not None:
            provider_env["KIMI_SNAPSHOT_ROOT"] = str(selected_root)
            args = (*args, "--add-dir", str(selected_root))
        admitted_entry = replace(entry, binary_name=str(record["binary_realpath"]))
        runtime = OneShotRuntime(
            homes_root=self._homes_root,
            manifest=(admitted_entry,),
            bundle_roots=(self._admission_root / "releases",),
            binary_search_roots=self._binary_search_roots,
        )
        run = runtime.one_shot_cli_run(
            admitted_entry.tool_id,
            args=args,
            provider_home=readiness["home"],
            provider_env=provider_env,
            timeout_seconds=admitted_entry.timeout_seconds,
            output_cap_bytes=admitted_entry.output_cap_bytes,
            allow_provider_network=True,
        )
        run_record = run.get("run") or {}
        stdout = run_record.get("stdout", "")
        parsed = parse_cli_output(
            str(stdout),
            profile="json_lines",
            output_cap_bytes=admitted_entry.output_cap_bytes,
        )
        output_valid = _kimi_stream_output_is_success(parsed, run_record)
        ok = run.get("status") == "ok" and output_valid
        return build_command_payload(
            ok=ok,
            human_message=(
                "Kimi production one-shot response received."
                if ok
                else "Kimi production one-shot response failed validation."
            ),
            machine_error_code=(
                ONE_SHOT_OK
                if ok
                else ONE_SHOT_OUTPUT_INVALID
                if run.get("status") == "ok"
                else str(run.get("machine_error_code") or ONE_SHOT_RUN_FAILED)
            ),
            liveness="healthy",
            severity="info" if ok else "error",
            operator_action="none" if ok else "user_action",
            changed_files=[str(readiness["home"])],
            exit_code=0 if ok else 1,
            extra={
                "surface": "run_prompt",
                "tool_id": entry.tool_id,
                "provider_id": entry.provider_id,
                "run": run.get("run"),
                "parsed_output": parsed,
                "production_admission_revalidated": True,
                "manifest_sha256": manifest_entry_digest(entry),
                "binary_sha256": record["binary_sha256"],
                "auth_present": True,
                "auth_presence_only": True,
                "secret_value_exposed": False,
                "provider_home_may_change": True,
                "provider_network_allowed": True,
                "repo_write_policy": "denied",
                **root_fields,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def run_prompt(
        self,
        tool_id: str,
        prompt_text: str,
        *,
        active_project_root: Path | str | None = None,
    ) -> dict[str, Any]:
        """Run one sealed provider prompt without exposing a caller argv path."""
        entry = self._entry_for_tool(tool_id)
        if entry is None:
            return self._unknown_packet("run_prompt", tool_id=str(tool_id))
        prompt = str(prompt_text or "")
        prompt_max_chars = (
            KIMI_PROMPT_MAX_CHARS if entry.provider_id == "kimi" else QWEN_PROMPT_MAX_CHARS
        )
        if (
            not prompt.strip()
            or "\x00" in prompt
            or len(prompt) > prompt_max_chars
        ):
            return self._blocked_packet(
                "run_prompt",
                ONE_SHOT_SCHEMA_INVALID,
                "prompt_empty_nul_or_oversized",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                prompt_max_chars=prompt_max_chars,
            )
        if _contains_secret_shape(prompt):
            return self._blocked_packet(
                "run_prompt",
                ONE_SHOT_SECRET_INPUT_BLOCKED,
                "prompt_secret_shape_blocked",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                input_blocked=True,
                secret_value_exposed=False,
            )
        blocked = self._declaration_block("run_prompt", entry)
        if blocked is not None:
            return blocked
        blocked = self._adapter_block("run_prompt", entry)
        if blocked is not None:
            return blocked
        if entry.provider_id == "kimi":
            return self._run_kimi_prompt(
                entry,
                prompt,
                active_project_root=active_project_root,
            )
        if (
            entry.provider_id != "qwen"
            or entry.allowed_argv_schema != QWEN_ALLOWED_ARGV_SCHEMA
            or entry.operational_args != QWEN_OPERATIONAL_ARGS
        ):
            return self._blocked_packet(
                "run_prompt",
                ONE_SHOT_SCHEMA_INVALID,
                "qwen_headless_argv_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        if (
            entry.network_policy != QWEN_NETWORK_POLICY
            or entry.sandbox_policy != QWEN_SANDBOX_POLICY
        ):
            return self._blocked_packet(
                "run_prompt",
                CLI_NETWORK_POLICY_NOT_ADMITTED,
                "qwen_provider_network_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                network_policy=entry.network_policy,
                sandbox_policy=entry.sandbox_policy,
            )
        if entry.auth_strategy != QWEN_AUTH_STRATEGY:
            return self._blocked_packet(
                "run_prompt",
                CLI_AUTH_NOT_ADMITTED,
                "qwen_auth_contract_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
            )
        record, blocked = self._read_target_admission("run_prompt", entry)
        if blocked is not None:
            return blocked
        assert record is not None
        readiness, blocked = self._qwen_home_readiness("run_prompt", entry)
        if blocked is not None:
            return blocked
        assert readiness is not None

        selected_root: Path | None = None
        root_fields: dict[str, Any] = {
            "active_project_root_required": False,
            "active_project_root_available": False,
            "active_project_root_source": "not_requested",
            "active_project_root_status": "not_requested",
            "active_project_root_path_recorded": False,
            "active_project_root_sha256": "",
            "active_project_root_is_wbp_repo": False,
            "active_project_root_git_available": False,
            "active_project_root_fallback_used": False,
            "active_project_root_legacy_target_repo_alias_used": False,
        }
        if active_project_root is not None:
            selected_root, root_fields = active_root.active_project_root_metadata(
                active_project_root,
                source="production_one_shot_prompt",
                wbp_repo_root=Path(__file__).resolve().parents[1],
                required=True,
            )
            if selected_root is None:
                return self._blocked_packet(
                    "run_prompt",
                    ONE_SHOT_PATH_VIOLATION,
                    str(root_fields["active_project_root_status"]),
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                    **root_fields,
                )

        provider_env = {
            "QWEN_HOME": str(readiness["home"]),
            "QWEN_RUNTIME_DIR": str(readiness["runtime_dir"]),
            **QWEN_FIXED_ENV,
        }
        if selected_root is not None:
            provider_env["QWEN_PROJECT_ROOT"] = str(selected_root)
        admitted_entry = replace(entry, binary_name=str(record["binary_realpath"]))
        runtime = OneShotRuntime(
            homes_root=self._homes_root,
            manifest=(admitted_entry,),
            bundle_roots=(self._admission_root / "releases",),
            binary_search_roots=self._binary_search_roots,
        )
        run = runtime.one_shot_cli_run(
            admitted_entry.tool_id,
            args=("--prompt", prompt, *admitted_entry.operational_args),
            provider_home=readiness["home"],
            provider_env=provider_env,
            timeout_seconds=admitted_entry.timeout_seconds,
            output_cap_bytes=admitted_entry.output_cap_bytes,
            allow_provider_network=True,
        )
        stdout = (run.get("run") or {}).get("stdout", "")
        parsed = parse_cli_output(
            str(stdout),
            profile="json",
            output_cap_bytes=admitted_entry.output_cap_bytes,
        )
        run_record = run.get("run") or {}
        output_valid = _qwen_json_output_is_success(parsed, run_record)
        ok = run.get("status") == "ok" and output_valid
        return build_command_payload(
            ok=ok,
            human_message=(
                "Qwen production one-shot response received."
                if ok
                else "Qwen production one-shot response failed validation."
            ),
            machine_error_code=(
                ONE_SHOT_OK
                if ok
                else (
                    ONE_SHOT_OUTPUT_INVALID
                    if run.get("status") == "ok"
                    else str(run.get("machine_error_code") or ONE_SHOT_RUN_FAILED)
                )
            ),
            liveness="healthy",
            severity="info" if ok else "error",
            operator_action="none" if ok else "user_action",
            changed_files=[str(readiness["home"])],
            exit_code=0 if ok else 1,
            extra={
                "surface": "run_prompt",
                "tool_id": entry.tool_id,
                "provider_id": entry.provider_id,
                "run": run.get("run"),
                "parsed_output": parsed,
                "production_admission_revalidated": True,
                "manifest_sha256": manifest_entry_digest(entry),
                "binary_sha256": record["binary_sha256"],
                "auth_present": True,
                "auth_presence_only": True,
                "secret_value_exposed": False,
                "provider_home_may_change": True,
                "provider_network_allowed": True,
                "repo_write_policy": "denied",
                **root_fields,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def run(self, tool_id: str) -> dict[str, Any]:
        entry = self._entry_for_tool(tool_id)
        if entry is None:
            return self._unknown_packet("run", tool_id=str(tool_id))
        blocked = self._declaration_block("run", entry)
        if blocked is not None:
            return blocked
        blocked = self._adapter_block("run", entry)
        if blocked is not None:
            return blocked
        if entry.network_policy != "denied":
            return self._blocked_packet(
                "run",
                CLI_NETWORK_POLICY_NOT_ADMITTED,
                "network_policy_not_admitted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                network_policy=entry.network_policy,
            )
        if entry.auth_strategy != "none":
            return self._blocked_packet(
                "run",
                CLI_AUTH_NOT_ADMITTED,
                "interactive_login_not_admitted",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                auth_strategy=entry.auth_strategy,
            )
        expected_schema = tuple(f"literal:{arg}" for arg in entry.operational_args)
        if entry.operational_args:
            argv_contract_ok = all(
                token in entry.allowed_argv_schema for token in expected_schema
            )
        else:
            argv_contract_ok = "no_args" in entry.allowed_argv_schema
        if not argv_contract_ok:
            return self._blocked_packet(
                "run",
                ONE_SHOT_SCHEMA_INVALID,
                "declaration_argv_schema_invalid",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        record, blocked = self._read_target_admission("run", entry)
        if blocked is not None:
            return blocked
        assert record is not None
        admitted_entry = replace(entry, binary_name=str(record["binary_realpath"]))
        runtime = OneShotRuntime(
            homes_root=self._homes_root,
            manifest=(admitted_entry,),
            bundle_roots=(self._admission_root / "releases",),
            binary_search_roots=self._binary_search_roots,
        )
        packet = runtime.one_shot_cli_run(
            admitted_entry.tool_id,
            args=admitted_entry.operational_args,
            timeout_seconds=admitted_entry.timeout_seconds,
            output_cap_bytes=admitted_entry.output_cap_bytes,
        )
        packet["production_admission_revalidated"] = True
        packet["manifest_sha256"] = manifest_entry_digest(entry)
        packet["binary_sha256"] = record["binary_sha256"]
        return packet

    def admit(
        self,
        tool_id: str,
        *,
        expected_binary_sha256: str,
    ) -> dict[str, Any]:
        """Probe and atomically admit one exact executable digest."""
        entry = self._entry_for_tool(tool_id)
        if entry is None:
            return self._unknown_packet("admit", tool_id=str(tool_id))
        blocked = self._declaration_block("admit", entry)
        if blocked is not None:
            return blocked
        expected = str(expected_binary_sha256 or "")
        if not _SHA256_RE.fullmatch(expected):
            return self._blocked_packet(
                "admit",
                ONE_SHOT_SCHEMA_INVALID,
                "expected_binary_sha256_invalid",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        probe = self.probe(entry.tool_id)
        if probe.get("status") != "ok":
            return probe
        if probe.get("binary_sha256") != expected:
            return self._blocked_packet(
                "admit",
                CLI_ADMISSION_DIGEST_MISMATCH,
                "expected_binary_digest_mismatch",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
                observed_binary_sha256=probe.get("binary_sha256"),
            )
        realpath, identity_reason = _validate_server_owned_binary(
            str(probe.get("realpath", ""))
        )
        if realpath is None:
            return self._blocked_packet(
                "admit",
                CLI_BINARY_ADMISSION_INVALID,
                identity_reason,
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        version_text = str(probe.get("version_text", "")).strip()
        if not version_text:
            return self._blocked_packet(
                "admit",
                CLI_BINARY_ADMISSION_INVALID,
                "version_identity_empty",
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        binary_info = Path(realpath).stat()
        bundle_root = _managed_bundle_root(
            realpath,
            bundle_roots=(self._admission_root / "releases",),
        )
        bundle_sha256 = ""
        bundle_file_count = 0
        bundle_total_bytes = 0
        if bundle_root is not None:
            try:
                (
                    bundle_sha256,
                    bundle_file_count,
                    bundle_total_bytes,
                ) = compute_bundle_digest(bundle_root)
            except (OSError, ValueError) as exc:
                return self._blocked_packet(
                    "admit",
                    CLI_BINARY_ADMISSION_INVALID,
                    str(exc) or "bundle_identity_unreadable_or_unsafe",
                    tool_id=entry.tool_id,
                    provider_id=entry.provider_id,
                )
        record = {
            "tool_id": entry.tool_id,
            "provider_id": entry.provider_id,
            "manifest_sha256": manifest_entry_digest(entry),
            "binary_realpath": realpath,
            "binary_sha256": expected,
            "binary_uid": binary_info.st_uid,
            "binary_mode": oct(stat.S_IMODE(binary_info.st_mode)),
            "bundle_root_realpath": str(bundle_root) if bundle_root is not None else "",
            "bundle_sha256": bundle_sha256,
            "bundle_file_count": bundle_file_count,
            "bundle_total_bytes": bundle_total_bytes,
            "version_text": version_text,
            "observed_at_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }
        ok, code, reason, changed = _write_admission_record(
            self._admission_root, record
        )
        if not ok:
            return self._blocked_packet(
                "admit",
                code,
                reason,
                changed_files=changed,
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        readback = _read_admission_store(self._admission_root)
        if not readback.ok or readback.records.get(entry.tool_id) != record:
            return self._blocked_packet(
                "admit",
                CLI_BINARY_ADMISSION_INVALID,
                "admission_readback_failed",
                changed_files=changed,
                tool_id=entry.tool_id,
                provider_id=entry.provider_id,
            )
        return build_command_payload(
            ok=True,
            human_message=f"exact binary admitted for '{entry.tool_id}'.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=changed,
            exit_code=0,
            extra={
                "surface": "admit",
                "tool_id": entry.tool_id,
                "provider_id": entry.provider_id,
                "manifest_sha256": record["manifest_sha256"],
                "binary_realpath": realpath,
                "binary_sha256": expected,
                "bundle_root_realpath": record["bundle_root_realpath"],
                "bundle_sha256": record["bundle_sha256"],
                "bundle_file_count": record["bundle_file_count"],
                "bundle_total_bytes": record["bundle_total_bytes"],
                "version_text": version_text,
                "admission_record_sha256": hashlib.sha256(
                    _canonical_json_bytes(record)
                ).hexdigest(),
                "provider_adapter_admitted": entry.provider_adapter_admitted,
                "probe_grants_operational_authority": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )

    def receipt(self) -> dict[str, Any]:
        """Read-only declaration/store receipt; it never probes or writes."""
        sandbox = probe_os_sandbox()
        store = _read_admission_store(self._admission_root)
        admitted_tool_ids: list[str] = []
        operational_candidates: list[str] = []
        for entry in self._manifest:
            record = store.records.get(entry.tool_id) if store.ok else None
            if record and record.get("manifest_sha256") == manifest_entry_digest(entry):
                admitted_tool_ids.append(entry.tool_id)
                if (
                    entry.provider_adapter_admitted
                    and entry.auth_strategy == "none"
                    and entry.network_policy == "denied"
                ):
                    operational_candidates.append(entry.tool_id)
        return build_command_payload(
            ok=True,
            human_message="Production one-shot CLI admission boundary is available.",
            machine_error_code=ONE_SHOT_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "schema_version": ONE_SHOT_RUNTIME_SCHEMA_VERSION,
                "admission_schema_version": ONE_SHOT_ADMISSION_SCHEMA_VERSION,
                "cli_disabled": False,
                "cli_operational": False,
                "production_admission_supported": True,
                "declared_not_live_verified": True,
                "server_owned_tools": [entry.to_dict() for entry in self._manifest],
                "server_owned_manifest_sha256": hashlib.sha256(
                    _canonical_json_bytes([entry.to_dict() for entry in self._manifest])
                ).hexdigest(),
                "homes_root": str(self._homes_root),
                "admission_root": str(self._admission_root),
                "admission_store_status": store.machine_error_code,
                "admission_store_reason": store.reason,
                "admitted_tool_ids": admitted_tool_ids,
                "operational_candidate_tool_ids": operational_candidates,
                "sterile_path": list(self._binary_search_roots),
                "sandbox": sandbox,
                "runtime_grant_available": False,
                "live_binary_revalidation_performed": False,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            },
        )


_PRODUCTION_FACADE: ProductionOneShotFacade | None = None
_PRODUCTION_FACADE_LOCK = threading.Lock()


def default_production_facade() -> ProductionOneShotFacade:
    """The singleton production facade (sealed server-owned config)."""
    global _PRODUCTION_FACADE
    with _PRODUCTION_FACADE_LOCK:
        if _PRODUCTION_FACADE is None:
            _PRODUCTION_FACADE = ProductionOneShotFacade()
        return _PRODUCTION_FACADE


def parse_cli_output(
    text: str,
    *,
    profile: str = "auto",
    output_cap_bytes: int = DEFAULT_OUTPUT_CAP_BYTES,
) -> dict[str, Any]:
    """Normalize CLI output without fabricating structure.

    - `text`: ANSI-stripped lines, capped
    - `key_value`: `name=value` lines only; unmatched lines counted honestly
    - `json`: one complete JSON document (object or array)
    - `json_lines`: JSON objects per line; mixed content is reported
    - `auto`: detect a complete JSON document, then json-lines, then
      key-value, else text; the detected format is always reported
    """
    profile = str(profile or "auto").strip()
    if profile not in {"auto", "text", "key_value", "json", "json_lines"}:
        raise RuntimeErrorInfo(
            "unknown CLI output profile.",
            machine_error_code="schema_invalid",
            operator_action="user_action",
        )
    safe_text = _redact_one_shot_text(text)
    cleaned = ANSI_ESCAPE_RE.sub("", safe_text)
    capped = cleaned[:output_cap_bytes]
    truncated = len(cleaned) > output_cap_bytes
    lines = [line.rstrip("\r") for line in capped.splitlines()]

    if profile in {"auto", "json"}:
        try:
            document = json.loads(capped)
        except ValueError:
            document = None
        if isinstance(document, (dict, list)) or profile == "json":
            return command_packets.redact_command_packet_value({
                "profile": profile,
                "detected_format": "json",
                "document": document,
                "valid": isinstance(document, (dict, list)),
                "truncated": truncated,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            })

    if profile in {"auto", "json_lines"}:
        records: list[dict[str, Any]] = []
        malformed = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except ValueError:
                malformed += 1
        if records or profile == "json_lines":
            detected = "json_lines"
            return command_packets.redact_command_packet_value({
                "profile": profile,
                "detected_format": detected,
                "records": records,
                "malformed_lines": malformed,
                "line_count": len(lines),
                "truncated": truncated,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            })

    if profile in {"auto", "key_value"}:
        pairs: dict[str, str] = {}
        unmatched = 0
        for line in lines:
            match = KEY_VALUE_LINE_RE.match(line.strip())
            if match:
                pairs[match.group(1)] = match.group(2)
            else:
                unmatched += 1
        if pairs or profile == "key_value":
            detected = "key_value"
            return command_packets.redact_command_packet_value({
                "profile": profile,
                "detected_format": detected,
                "pairs": pairs,
                "unmatched_lines": unmatched,
                "line_count": len(lines),
                "truncated": truncated,
                "resume_supported": False,
                "resume_reason": ONE_SHOT_NO_RESUME_REASON,
            })

    return command_packets.redact_command_packet_value({
        "profile": profile,
        "detected_format": "text",
        "text": "\n".join(lines),
        "line_count": len(lines),
        "truncated": truncated,
        "resume_supported": False,
        "resume_reason": ONE_SHOT_NO_RESUME_REASON,
    })
