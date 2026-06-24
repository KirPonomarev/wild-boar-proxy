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
import re
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any

from .core import packets
from .external_models import errors, transforms
from .external_models.http_client import request_json
from .external_models.paths import ExternalModelsPaths
from .external_models.routes import find_route, load_routes_file
from .external_models.validate import _completion_url, _provider_headers
from .runtime import RuntimeErrorInfo, write_json_atomic, write_text_atomic


WBP_DIP_TOOL_PACKET_KIND = "wbp_dip_working_tool_run"
DEFAULT_ALIAS = "DIP"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_SANDBOX = "danger-full-access"
DEFAULT_CODEX_APP_NAME = "Codex WBP Clean.app"
STALE_CODEX_PROFILE_MODEL_IDS = frozenset({"gpt-5.3-codex"})
DEFAULT_ENTRY_EVIDENCE_FILENAME = "mcp-entry-evidence.json"
DEFAULT_CODEX_JSONL_FILENAME = "codex-exec.jsonl"
DEFAULT_LAST_MESSAGE_FILENAME = "last-message.txt"
DEFAULT_LIVE_RESULT_TEXT_ARTIFACT_FILENAME = "live-result-full-text.txt"
DEFAULT_LIVE_RESULT_TIMEOUT_SECONDS = 60.0
DEFAULT_BRIDGE_TIMEOUT_SECONDS = 8.0
DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS = 2.0
DEFAULT_LIVE_RESULT_TEXT_LIMIT = 2400
FULL_WORK_LIVE_RESULT_TEXT_LIMIT = 64000
DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS = 768
FULL_WORK_MAX_OUTPUT_TOKENS = 32768
DEFAULT_REPO_BRIDGE_MODE = "auto"
DEFAULT_REPO_BRIDGE_MAX_STEPS = 8
FULL_WORK_REPO_BRIDGE_MAX_STEPS = 24
DEFAULT_REPO_BRIDGE_FILE_TEXT_LIMIT = 12000
DEFAULT_REPO_BRIDGE_CONTEXT_TEXT_LIMIT = 18000
DEFAULT_REPO_BRIDGE_TOOL_RESULT_TEXT_LIMIT = 16000
DEFAULT_REPO_BRIDGE_SEARCH_LINE_LIMIT = 80
DEFAULT_REPO_BRIDGE_FILE_LIST_LIMIT = 400
DEFAULT_ACTION_COMMAND_TIMEOUT_SECONDS = 60.0
DEFAULT_ACTION_PATCH_TEXT_LIMIT = 120000
MIN_SUPPORTED_PYTHON = (3, 10)
PYTHON_BIN_ENV = "WBP_PYTHON_BIN"

WBP_DIP_TOOL_OK = "OK"
WBP_DIP_TOOL_DRY_RUN = "WBP_DIP_TOOL_DRY_RUN"
WBP_DIP_TOOL_TASK_REQUIRED = "WBP_DIP_TOOL_TASK_REQUIRED"
WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE = "WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE"
WBP_DIP_TOOL_CODEX_EXEC_FAILED = "WBP_DIP_TOOL_CODEX_EXEC_FAILED"
WBP_DIP_TOOL_DELEGATE_NOT_PROVEN = "WBP_DIP_TOOL_DELEGATE_NOT_PROVEN"
WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE = "WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE"
WBP_DIP_TOOL_UNSAFE_PACKET = "WBP_DIP_TOOL_UNSAFE_PACKET"
WBP_DIP_TOOL_LIVE_RESULT_UNSAFE = "WBP_DIP_TOOL_LIVE_RESULT_UNSAFE"
WBP_DIP_TOOL_ALIAS_NOT_IN_CONTEXT = "WBP_DIP_TOOL_ALIAS_NOT_IN_CONTEXT"
WBP_DIP_TOOL_ROUTE_NOT_ALLOWED = "WBP_DIP_TOOL_ROUTE_NOT_ALLOWED"
WBP_DIP_TOOL_ROUTE_CONTEXT_MISSING = "WBP_DIP_TOOL_ROUTE_CONTEXT_MISSING"
WBP_DIP_TOOL_REPO_BRIDGE_UNAVAILABLE = "WBP_DIP_TOOL_REPO_BRIDGE_UNAVAILABLE"
WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED = "WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED"
WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED = "WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED"
WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED = "WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED"
WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN = "WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN"

REPO_BRIDGE_MODES = ("auto", "on", "off")
DIP_WORK_MODES = ("standard", "full")
DEFAULT_DIP_WORK_MODE = "standard"
REPO_BRIDGE_TASK_KEYWORDS = (
    "repo",
    "repository",
    "codebase",
    "project",
    "files",
    "tests",
    "audit",
    "review",
    "репо",
    "репозитор",
    "проект",
    "код",
    "файл",
    "тест",
    "аудит",
    "изучи",
    "изучить",
    "отчет",
)
ACTION_BRIDGE_TASK_KEYWORDS = (
    "fix",
    "repair",
    "implement",
    "patch",
    "change",
    "edit",
    "test",
    "verify",
    "run",
    "почини",
    "чинить",
    "исправь",
    "исправить",
    "реализуй",
    "реализовать",
    "сделай",
    "доделай",
    "патч",
    "тест",
    "проверь",
    "запусти",
)
CODE_MUTATION_TASK_KEYWORDS = (
    "fix",
    "repair",
    "implement",
    "patch",
    "change",
    "edit",
    "write code",
    "почини",
    "чинить",
    "исправь",
    "исправить",
    "реализуй",
    "реализовать",
    "доделай",
    "добавь",
    "создай",
    "напиши",
    "патч",
)
CODE_MUTATION_NEGATED_PHRASES = (
    "do not edit",
    "do not change",
    "do not modify",
    "don't edit",
    "don't change",
    "don't modify",
    "without editing",
    "without changing",
    "не редактируй",
    "не изменяй",
    "не меняй",
)
REPO_BRIDGE_PATH_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])"
    r"([A-Za-z0-9_./-]+\.(?:"
    r"py|md|js|ts|tsx|jsx|json|toml|yaml|yml|txt|css|html|sh|rs|go|java|rb|swift|kt|sql"
    r"))"
    r"(?![A-Za-z0-9_./-])",
    re.IGNORECASE,
)
ACTION_BRIDGE_TOOLS = {
    "propose_patch",
    "apply_patch",
    "run_tests",
    "run_command",
}
ACTION_ALLOWED_COMMAND_PREFIXES = (
    ("python3", "-m", "unittest"),
    ("python3", "-m", "pytest"),
    ("python3", "-m", "py_compile"),
    ("git", "diff", "--check"),
    ("git", "diff", "--stat"),
    ("git", "status"),
    ("rg",),
)
REPO_BRIDGE_CANONICAL_FILES = (
    "AGENTS.md",
    "CANON.md",
    "RUNTIME_CONTRACT.md",
    "COMMAND_API.md",
    "STATE_SCHEMA.md",
    "DELIVERY_RULES.md",
    "README.md",
)
REPO_BRIDGE_SENSITIVE_PART_NAMES = {
    ".git",
    ".env",
    ".ssh",
    ".gnupg",
    "__pycache__",
    "node_modules",
}
REPO_BRIDGE_SENSITIVE_NAME_MARKERS = (
    "secret",
    "credential",
    "token",
    "private_key",
    "private-key",
    "api_key",
    "api-key",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _safe_int(
    value: object,
    *,
    default: int = 0,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(number, minimum)
    if maximum is not None:
        number = min(number, maximum)
    return number


def _dip_work_mode_settings(work_mode: str) -> dict[str, int | str]:
    mode = _safe_text(work_mode, limit=40)
    if mode not in DIP_WORK_MODES:
        mode = DEFAULT_DIP_WORK_MODE
    if mode == "full":
        return {
            "dip_work_mode": "full",
            "live_result_text_limit": FULL_WORK_LIVE_RESULT_TEXT_LIMIT,
            "output_token_limit": FULL_WORK_MAX_OUTPUT_TOKENS,
            "repo_bridge_max_steps": FULL_WORK_REPO_BRIDGE_MAX_STEPS,
        }
    return {
        "dip_work_mode": DEFAULT_DIP_WORK_MODE,
        "live_result_text_limit": DEFAULT_LIVE_RESULT_TEXT_LIMIT,
        "output_token_limit": DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS,
        "repo_bridge_max_steps": DEFAULT_REPO_BRIDGE_MAX_STEPS,
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _repair_stale_profile_config_model(profile_dir: Path, *, model: str) -> dict[str, Any]:
    target_model = _safe_text(model, limit=120)
    packet = {
        "profile_config_model_repair_attempted": False,
        "profile_config_model_repaired": False,
        "profile_config_model_before": "",
        "profile_config_model_after": "",
        "profile_config_model_target": target_model,
        "profile_config_path_recorded": False,
        "profile_config_repair_error": "",
    }
    if not target_model or target_model in STALE_CODEX_PROFILE_MODEL_IDS:
        return packet
    config_path = profile_dir / "config.toml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**packet, "profile_config_repair_error": "config_missing"}
    except OSError:
        return {**packet, "profile_config_repair_error": "config_read_failed"}
    match = re.search(r'(?m)^model\s*=\s*"([^"]*)"', text)
    current_model = _safe_text(match.group(1), limit=120) if match else ""
    packet["profile_config_model_before"] = current_model
    packet["profile_config_model_after"] = current_model
    if current_model not in STALE_CODEX_PROFILE_MODEL_IDS:
        return packet
    repaired = re.sub(
        r'(?m)^model\s*=\s*"[^"]*"',
        f'model = "{target_model}"',
        text,
        count=1,
    )
    try:
        write_text_atomic(config_path, repaired.rstrip("\n"))
    except OSError:
        return {
            **packet,
            "profile_config_model_repair_attempted": True,
            "profile_config_repair_error": "config_write_failed",
        }
    return {
        **packet,
        "profile_config_model_repair_attempted": True,
        "profile_config_model_repaired": True,
        "profile_config_model_after": target_model,
        "profile_config_repair_error": "",
    }


def _merge_profile_config_repair_packets(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "profile_config_model_repair_attempted": (
            before.get("profile_config_model_repair_attempted") is True
            or after.get("profile_config_model_repair_attempted") is True
        ),
        "profile_config_model_repaired": (
            before.get("profile_config_model_repaired") is True
            or after.get("profile_config_model_repaired") is True
        ),
        "profile_config_model_repaired_before_codex_exec": (
            before.get("profile_config_model_repaired") is True
        ),
        "profile_config_model_repaired_after_codex_exec": (
            after.get("profile_config_model_repaired") is True
        ),
        "profile_config_model_before": _safe_text(
            before.get("profile_config_model_before"),
            limit=120,
        ),
        "profile_config_model_after": _safe_text(
            after.get("profile_config_model_after")
            or before.get("profile_config_model_after"),
            limit=120,
        ),
        "profile_config_model_target": _safe_text(
            after.get("profile_config_model_target")
            or before.get("profile_config_model_target"),
            limit=120,
        ),
        "profile_config_path_recorded": False,
        "profile_config_repair_error": _safe_text(
            after.get("profile_config_repair_error")
            or before.get("profile_config_repair_error"),
            limit=120,
        ),
    }


def _provider_proof_fields(*, direct_provider_response_observed: bool) -> dict[str, Any]:
    return {
        "direct_provider_auth_proven": bool(direct_provider_response_observed),
        "direct_provider_response_observed": bool(direct_provider_response_observed),
        "provider_auth_ok": bool(direct_provider_response_observed),
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": bool(direct_provider_response_observed),
    }


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


def _codex_app_candidates(source: Mapping[str, str]) -> list[Path]:
    app_candidates: list[Path] = []
    if source.get("WBP_CODEX_APP_COPY_PATH"):
        app_candidates.append(Path(str(source["WBP_CODEX_APP_COPY_PATH"])).expanduser())
    app_candidates.extend(
        [
            Path.home() / "Applications" / DEFAULT_CODEX_APP_NAME,
            Path("/Applications") / DEFAULT_CODEX_APP_NAME,
            Path.home() / "Applications" / "Codex.app",
            Path("/Applications/Codex.app"),
        ]
    )
    return app_candidates


def default_codex_bin(env: Mapping[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    if source.get("WBP_CODEX_BIN"):
        return Path(str(source["WBP_CODEX_BIN"])).expanduser()
    binary_candidates = [
        app / "Contents/Resources/codex"
        for app in _codex_app_candidates(source)
    ]
    for candidate in binary_candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    path_codex = shutil.which("codex")
    if path_codex:
        return Path(path_codex).expanduser()
    return binary_candidates[0]


def _python_candidate_names() -> tuple[str, ...]:
    return ("python3.14", "python3.13", "python3.12", "python3.11", "python3.10")


def _python_candidate_absolute_paths() -> tuple[str, ...]:
    return (
        "/opt/homebrew/opt/python@3.14/bin/python3.14",
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
    )


def default_python_bin(env: Mapping[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    if source.get(PYTHON_BIN_ENV):
        return Path(str(source[PYTHON_BIN_ENV])).expanduser()
    if sys.version_info >= MIN_SUPPORTED_PYTHON:
        return Path(sys.executable).expanduser()
    for name in _python_candidate_names():
        found = shutil.which(name)
        if found:
            return Path(found).expanduser()
    for raw_path in _python_candidate_absolute_paths():
        candidate = Path(raw_path)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return Path("python3")


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
    python_bin: Path | None = None,
    repo_root: Path,
    model: str,
    sandbox: str,
    prompt: str,
    output_jsonl: Path,
    output_last_message: Path,
    profile_dir: Path,
    entry_evidence_file: Path,
    extra_args: Sequence[str] = (),
    extra_mcp_env: Mapping[str, str] | None = None,
) -> list[str]:
    mcp_python_bin = python_bin or default_python_bin()
    env_table = {
        "PYTHONPATH": str(repo_root),
        "WBP_ENTRY_HOOK_EVIDENCE_PATH": str(entry_evidence_file),
        "WBP_PROFILE_DIR": str(profile_dir),
        PYTHON_BIN_ENV: str(mcp_python_bin),
    }
    if extra_mcp_env:
        env_table.update(
            {
                str(key): str(value)
                for key, value in extra_mcp_env.items()
                if key and value
            }
        )
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
        f"mcp_servers.wbp.command={_toml_string(str(mcp_python_bin))}",
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


def _delegate_packet_ok(delegate_packet: Mapping[str, Any]) -> bool:
    return bool(
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


def _load_runtime_context(profile_dir: Path) -> dict[str, Any]:
    context_path = profile_dir / "wbp-agent-runtime-context.json"
    try:
        parsed = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _casefold_lookup(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    wanted = key.casefold()
    for candidate_key, value in mapping.items():
        if str(candidate_key).casefold() == wanted:
            return value
    return None


def _runtime_route_for_alias(
    context: Mapping[str, Any],
    expected_alias: str,
) -> tuple[str, bool, str]:
    alias_to_agent_id = context.get("alias_to_agent_id")
    agent_id_to_route = context.get("agent_id_to_route")
    allowed_route_ids = context.get("allowed_api_route_ids")
    allowed = {
        str(route_id)
        for route_id in allowed_route_ids
        if str(route_id).strip()
    } if isinstance(allowed_route_ids, list) else set()
    if not isinstance(alias_to_agent_id, Mapping):
        return "", False, "alias_context_missing"
    agent_id = (
        _casefold_lookup(alias_to_agent_id, expected_alias)
        if expected_alias
        else None
    )
    if not agent_id:
        return "", False, "alias_not_in_context"
    if not isinstance(agent_id_to_route, Mapping):
        return "", False, "route_context_missing"
    route_id = (
        _casefold_lookup(agent_id_to_route, str(agent_id))
        if agent_id
        else None
    )
    route_text = _safe_text(route_id, limit=160)
    if not route_text:
        return "", False, "route_missing"
    if route_text not in allowed:
        return route_text, False, "route_not_allowed"
    return route_text, True, "ok"


def _route_status_machine_error_code(route_status: str) -> str:
    if route_status == "alias_context_missing":
        return "FAIL_ALIAS_CONTEXT_MISSING"
    if route_status == "alias_not_in_context":
        return WBP_DIP_TOOL_ALIAS_NOT_IN_CONTEXT
    if route_status == "route_context_missing":
        return WBP_DIP_TOOL_ROUTE_CONTEXT_MISSING
    if route_status == "route_not_allowed":
        return WBP_DIP_TOOL_ROUTE_NOT_ALLOWED
    return WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE


def _task_contains_keyword(task_key: str, keywords: Sequence[str]) -> bool:
    for keyword in keywords:
        keyword_key = keyword.casefold()
        ascii_wordish = all(
            char.isascii() and (char.isalnum() or char in {"_", " "})
            for char in keyword_key
        )
        if ascii_wordish:
            pattern = rf"(?<![a-z0-9_]){re.escape(keyword_key)}(?![a-z0-9_])"
            if re.search(pattern, task_key):
                return True
            continue
        if keyword_key in task_key:
            return True
    return False


def _task_path_candidates(task: str, *, limit: int = 4) -> list[str]:
    candidates: list[str] = []
    for match in REPO_BRIDGE_PATH_PATTERN.finditer(task):
        candidate = match.group(1).strip("`'\".,:;()[]{}")
        if candidate and candidate not in candidates:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def _repo_bridge_bootstrap_calls(
    *,
    task: str,
    repo_bridge_required: bool,
    action_bridge_required: bool,
) -> list[dict[str, Any]]:
    if not repo_bridge_required:
        return []
    path_calls = [
        {"tool": "read_file", "path": candidate, "origin": "wbp_bootstrap"}
        for candidate in _task_path_candidates(task)
    ]
    if path_calls:
        return path_calls
    if action_bridge_required:
        return [{"tool": "git_status", "origin": "wbp_bootstrap"}]
    return [{"tool": "list_files", "path": ".", "origin": "wbp_bootstrap"}]


def _repo_bridge_requested(*, task: str, mode: str) -> bool:
    safe_mode = mode if mode in REPO_BRIDGE_MODES else DEFAULT_REPO_BRIDGE_MODE
    if safe_mode == "on":
        return True
    if safe_mode == "off":
        return False
    task_key = task.casefold()
    auto_keywords = (
        REPO_BRIDGE_TASK_KEYWORDS
        + tuple(
            keyword
            for keyword in ACTION_BRIDGE_TASK_KEYWORDS
            if keyword not in {"проверь", "run", "verify", "запусти"}
        )
        + CODE_MUTATION_TASK_KEYWORDS
    )
    return _task_contains_keyword(task_key, auto_keywords)


def _action_bridge_requested(*, task: str, repo_bridge_required: bool) -> bool:
    if not repo_bridge_required:
        return False
    task_key = task.casefold()
    return _task_contains_keyword(task_key, ACTION_BRIDGE_TASK_KEYWORDS)


def _code_mutation_requested(*, task: str, action_required: bool) -> bool:
    if not action_required:
        return False
    task_key = task.casefold()
    normalized_task_key = task_key
    for phrase in CODE_MUTATION_NEGATED_PHRASES:
        normalized_task_key = normalized_task_key.replace(phrase, "")
    return _task_contains_keyword(normalized_task_key, CODE_MUTATION_TASK_KEYWORDS)


def _path_is_sensitive(relative_path: str) -> bool:
    parts = [part.casefold() for part in Path(relative_path).parts]
    if any(part in REPO_BRIDGE_SENSITIVE_PART_NAMES for part in parts):
        return True
    name = Path(relative_path).name.casefold()
    if name.startswith(".env"):
        return True
    return any(marker in name for marker in REPO_BRIDGE_SENSITIVE_NAME_MARKERS)


def _repo_relative_path(repo_root: Path, raw_path: object) -> tuple[Path | None, str, str]:
    text = _safe_text(raw_path, limit=500)
    if not text:
        text = "."
    candidate = (repo_root / text).expanduser().resolve(strict=False)
    root = repo_root.expanduser().resolve(strict=False)
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None, "", "path_outside_repo"
    relative_text = "." if str(relative) == "." else str(relative)
    if _path_is_sensitive(relative_text):
        return None, relative_text, "path_blocked_sensitive"
    return candidate, relative_text, "ok"


def _bounded_repo_text(value: object, *, limit: int = DEFAULT_REPO_BRIDGE_TOOL_RESULT_TEXT_LIMIT) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()[:limit]


def _run_repo_process(
    argv: Sequence[str],
    *,
    repo_root: Path,
    timeout_seconds: float = 5.0,
) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, _safe_text(exc, limit=500)
    return int(completed.returncode), _bounded_repo_text(completed.stdout)


def _command_from_call(call: Mapping[str, Any]) -> list[str]:
    raw_args = call.get("args")
    if isinstance(raw_args, list):
        if len(raw_args) == 1:
            single_arg = _safe_text(raw_args[0], limit=2000)
            if single_arg and any(char.isspace() for char in single_arg):
                try:
                    return [part for part in shlex.split(single_arg) if part]
                except ValueError:
                    return []
        args = [_safe_text(item, limit=500) for item in raw_args]
        return [arg for arg in args if arg]
    raw_command = _safe_text(call.get("command"), limit=2000)
    if not raw_command:
        return []
    try:
        return shlex.split(raw_command)
    except ValueError:
        return []


def _command_allowed(argv: Sequence[str]) -> tuple[bool, str]:
    if not argv:
        return False, "command_required"
    if any(not part or "\x00" in part for part in argv):
        return False, "command_invalid"
    command = Path(argv[0]).name
    normalized = (command, *tuple(argv[1:]))
    for prefix in ACTION_ALLOWED_COMMAND_PREFIXES:
        if len(normalized) >= len(prefix) and normalized[: len(prefix)] == prefix:
            if command == "rg" and any(part.startswith("-r") or part == "--replace" for part in argv[1:]):
                return False, "rg_replace_not_allowed"
            return True, "ok"
    return False, "command_not_allowlisted"


def _run_action_command(repo_root: Path, call: Mapping[str, Any]) -> dict[str, Any]:
    argv = _command_from_call(call)
    allowed, reason = _command_allowed(argv)
    if not allowed:
        return {
            "status": "error",
            "machine_error_code": reason,
            "result_text": "",
            "command_exit_code": None,
        }
    code, output = _run_repo_process(
        argv,
        repo_root=repo_root,
        timeout_seconds=DEFAULT_ACTION_COMMAND_TIMEOUT_SECONDS,
    )
    return {
        "status": "ok" if code == 0 else "error",
        "machine_error_code": "OK" if code == 0 else "command_failed",
        "result_text": output,
        "command_exit_code": code,
        "command_sha256": _sha256_text(json.dumps(list(argv), separators=(",", ":"))),
        "command_recorded": False,
    }


def _run_tests(repo_root: Path, call: Mapping[str, Any]) -> dict[str, Any]:
    if not call.get("args") and not call.get("command"):
        call = {"args": ["python3", "-m", "unittest"]}
    return _run_action_command(repo_root, call)


def _patch_text_from_call(call: Mapping[str, Any]) -> str:
    patch_text = str(call.get("patch") or call.get("diff") or "")
    return patch_text.replace("\r\n", "\n").replace("\r", "\n")[:DEFAULT_ACTION_PATCH_TEXT_LIMIT]


def _patch_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        candidate = ""
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                candidate = parts[2]
        elif line.startswith("--- ") or line.startswith("+++ "):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                candidate = parts[1]
        if not candidate or candidate == "/dev/null":
            continue
        if candidate.startswith("a/") or candidate.startswith("b/"):
            candidate = candidate[2:]
        candidate = candidate.split("\t", 1)[0].strip()
        if candidate and candidate not in paths:
            paths.append(candidate)
    return paths


def _patch_safety(repo_root: Path, patch_text: str) -> tuple[bool, str, list[str]]:
    if not patch_text.strip():
        return False, "patch_required", []
    if len(patch_text) >= DEFAULT_ACTION_PATCH_TEXT_LIMIT:
        return False, "patch_too_large", []
    touched = _patch_paths(patch_text)
    if not touched:
        return False, "patch_paths_missing", []
    for relative in touched:
        if relative.startswith("/") or ".." in Path(relative).parts:
            return False, "patch_path_unsafe", touched
        path, _relative, status = _repo_relative_path(repo_root, relative)
        if status != "ok" or path is None:
            return False, status, touched
    return True, "ok", touched


def _git_apply_patch(repo_root: Path, patch_text: str, *, apply: bool) -> dict[str, Any]:
    safe, reason, touched = _patch_safety(repo_root, patch_text)
    patch_sha256 = _sha256_text(patch_text) if patch_text else ""
    if not safe:
        return {
            "status": "error",
            "machine_error_code": reason,
            "result_text": "",
            "patch_sha256": patch_sha256,
            "patch_recorded": False,
            "touched_files": touched,
            "mutation_applied": False,
        }
    try:
        check = subprocess.run(
            ["git", "apply", "--check", "-"],
            cwd=str(repo_root),
            input=patch_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=DEFAULT_ACTION_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "error",
            "machine_error_code": "patch_check_exec_failed",
            "result_text": _safe_text(exc, limit=500),
            "patch_sha256": patch_sha256,
            "patch_recorded": False,
            "touched_files": touched,
            "mutation_applied": False,
        }
    check_output = _bounded_repo_text(check.stdout)
    if check.returncode != 0:
        return {
            "status": "error",
            "machine_error_code": "patch_check_failed",
            "result_text": check_output,
            "patch_sha256": patch_sha256,
            "patch_recorded": False,
            "touched_files": touched,
            "mutation_applied": False,
        }
    if not apply:
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "result_text": "Patch proposal validated by git apply --check.",
            "patch_sha256": patch_sha256,
            "patch_recorded": False,
            "touched_files": touched,
            "mutation_applied": False,
        }
    try:
        applied = subprocess.run(
            ["git", "apply", "-"],
            cwd=str(repo_root),
            input=patch_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=DEFAULT_ACTION_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "error",
            "machine_error_code": "patch_apply_exec_failed",
            "result_text": _safe_text(exc, limit=500),
            "patch_sha256": patch_sha256,
            "patch_recorded": False,
            "touched_files": touched,
            "mutation_applied": False,
        }
    output = _bounded_repo_text(applied.stdout)
    return {
        "status": "ok" if applied.returncode == 0 else "error",
        "machine_error_code": "OK" if applied.returncode == 0 else "patch_apply_failed",
        "result_text": output or ("Patch applied." if applied.returncode == 0 else ""),
        "patch_sha256": patch_sha256,
        "patch_recorded": False,
        "touched_files": touched,
        "mutation_applied": applied.returncode == 0,
    }


def _repo_file_list(repo_root: Path, *, limit: int = DEFAULT_REPO_BRIDGE_FILE_LIST_LIMIT) -> list[str]:
    rg = shutil.which("rg")
    files: list[str] = []
    if rg:
        code, output = _run_repo_process(
            [rg, "--files", "--hidden", "-g", "!.git", "-g", "!__pycache__"],
            repo_root=repo_root,
        )
        if code == 0:
            files = [line.strip() for line in output.splitlines() if line.strip()]
    if not files:
        root = repo_root.resolve(strict=False)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                relative = str(path.relative_to(root))
            except ValueError:
                continue
            files.append(relative)
            if len(files) >= limit * 2:
                break
    clean_files = [
        relative
        for relative in files
        if relative and not _path_is_sensitive(relative)
    ]
    return sorted(dict.fromkeys(clean_files))[:limit]


def _read_repo_file(repo_root: Path, raw_path: object) -> dict[str, Any]:
    path, relative, status = _repo_relative_path(repo_root, raw_path)
    if status != "ok" or path is None:
        return {
            "status": "error",
            "machine_error_code": status,
            "path": relative,
            "result_text": "",
        }
    if not path.is_file():
        return {
            "status": "error",
            "machine_error_code": "file_not_found",
            "path": relative,
            "result_text": "",
        }
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "status": "error",
            "machine_error_code": "file_read_failed",
            "path": relative,
            "result_text": _safe_text(exc, limit=500),
        }
    text = _bounded_repo_text(raw, limit=DEFAULT_REPO_BRIDGE_FILE_TEXT_LIMIT)
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "path": relative,
        "result_text": text,
        "result_text_sha256": _sha256_text(text),
        "result_text_truncated": len(raw) > len(text),
    }


def _search_repo(repo_root: Path, call: Mapping[str, Any]) -> dict[str, Any]:
    pattern = _safe_text(call.get("pattern"), limit=300)
    if not pattern:
        return {
            "status": "error",
            "machine_error_code": "pattern_required",
            "result_text": "",
        }
    rg = shutil.which("rg")
    if not rg:
        return {
            "status": "error",
            "machine_error_code": "rg_not_available",
            "result_text": "",
        }
    argv = [
        rg,
        "-n",
        "--hidden",
        "-g",
        "!.git",
        "-g",
        "!__pycache__",
    ]
    glob = _safe_text(call.get("glob"), limit=200)
    if glob:
        argv.extend(["-g", glob])
    argv.extend(["--", pattern])
    code, output = _run_repo_process(argv, repo_root=repo_root)
    lines = output.splitlines()
    visible_lines = [
        line
        for line in lines
        if not _path_is_sensitive(line.split(":", 1)[0])
    ][:DEFAULT_REPO_BRIDGE_SEARCH_LINE_LIMIT]
    text = "\n".join(visible_lines)
    return {
        "status": "ok" if code in {0, 1} else "error",
        "machine_error_code": "OK" if code in {0, 1} else "search_failed",
        "result_text": text,
        "result_text_sha256": _sha256_text(text),
        "result_line_count": len(visible_lines),
        "result_truncated": len(lines) > len(visible_lines),
    }


def _list_repo_files(repo_root: Path, call: Mapping[str, Any]) -> dict[str, Any]:
    prefix = _safe_text(call.get("path") or call.get("prefix"), limit=300)
    files = _repo_file_list(repo_root)
    if prefix and prefix != ".":
        files = [path for path in files if path == prefix or path.startswith(prefix.rstrip("/") + "/")]
    text = "\n".join(files)
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "result_text": text,
        "result_text_sha256": _sha256_text(text),
        "result_file_count": len(files),
        "result_truncated": len(files) >= DEFAULT_REPO_BRIDGE_FILE_LIST_LIMIT,
    }


def _git_status_repo(repo_root: Path) -> dict[str, Any]:
    code, output = _run_repo_process(
        ["git", "status", "--short", "--branch"],
        repo_root=repo_root,
    )
    return {
        "status": "ok" if code == 0 else "error",
        "machine_error_code": "OK" if code == 0 else "git_status_failed",
        "result_text": output,
        "result_text_sha256": _sha256_text(output),
    }


def _build_repo_context_pack(repo_root: Path) -> dict[str, Any]:
    files = _repo_file_list(repo_root)
    status = _git_status_repo(repo_root)
    excerpts: list[dict[str, Any]] = []
    remaining = DEFAULT_REPO_BRIDGE_CONTEXT_TEXT_LIMIT
    for relative in REPO_BRIDGE_CANONICAL_FILES:
        if remaining <= 0:
            break
        read = _read_repo_file(repo_root, relative)
        if read.get("status") != "ok":
            continue
        text = str(read.get("result_text") or "")[: min(remaining, 3500)]
        remaining -= len(text)
        excerpts.append(
            {
                "path": relative,
                "text": text,
                "text_sha256": _sha256_text(text),
                "text_truncated": read.get("result_text_truncated") is True
                or len(str(read.get("result_text") or "")) > len(text),
            }
        )
    pack = {
        "schema_version": 1,
        "source": "wbp_local_repo_action_bridge_context_pack",
        "repo_root_recorded": False,
        "repo_root_sha256": _sha256_text(str(repo_root.resolve(strict=False))),
        "git_status_text": status.get("result_text", ""),
        "file_count_observed": len(files),
        "file_list_sample": files[:240],
        "canonical_file_excerpts": excerpts,
        "sensitive_paths_blocked": True,
        "mutations_allowed": True,
        "mutation_tools": ["propose_patch", "apply_patch"],
        "command_tools": ["run_tests", "run_command"],
        "command_allowlist_recorded": False,
    }
    return pack


def _repo_context_pack_sha256(pack: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(pack, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _repo_bridge_prompt(context_pack: Mapping[str, Any]) -> str:
    return (
        "\n\nWBP action bridge: You have WBP-mediated access to the local "
        "repository through a strict JSON tool protocol. You do not have direct "
        "filesystem or shell access; WBP executes approved tools locally and "
        "returns evidence. For repository inspection/report tasks, request at "
        "least one repo tool before the final answer. For implementation/fix/test "
        "tasks, request action tools until the work is either completed or blocked. "
        "For implementation/fix/edit tasks, completion requires an apply_patch "
        "tool call that actually changes code followed by a successful run_tests "
        "or run_command verification; a final answer without both facts will be "
        "rejected by WBP. "
        "To request a tool, output only one JSON object and no prose:\n"
        '{"wbp_repo_tool_call":{"tool":"list_files","path":"wild_boar_proxy"}}\n'
        '{"wbp_repo_tool_call":{"tool":"read_file","path":"AGENTS.md"}}\n'
        '{"wbp_repo_tool_call":{"tool":"search","pattern":"delegate_to_dip","glob":"wild_boar_proxy/**/*.py"}}\n'
        '{"wbp_repo_tool_call":{"tool":"git_status"}}\n'
        '{"wbp_repo_tool_call":{"tool":"propose_patch","patch":"<unified diff>"}}\n'
        '{"wbp_repo_tool_call":{"tool":"apply_patch","patch":"<unified diff>"}}\n'
        '{"wbp_repo_tool_call":{"tool":"run_tests","args":["python3","-m","unittest","tests.test_wbp_dip_tool"]}}\n'
        '{"wbp_repo_tool_call":{"tool":"run_command","args":["git","diff","--check"]}}\n'
        "After WBP returns tool evidence, continue with another tool request or "
        "give the final answer. Initial WBP context pack follows; treat it as "
        "evidence, not as memory:\n"
        f"{json.dumps(context_pack, ensure_ascii=False, sort_keys=True)}"
    )


def _extract_repo_tool_call(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    candidates = [stripped]
    if "{" in stripped and "}" in stripped:
        candidates.append(stripped[stripped.find("{") : stripped.rfind("}") + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, Mapping):
            continue
        raw_call = parsed.get("wbp_repo_tool_call") or parsed.get("tool_call")
        if isinstance(raw_call, Mapping):
            return dict(raw_call)
        if parsed.get("tool"):
            return dict(parsed)
    return {}


def _execute_repo_tool_call(call: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    tool = _safe_text(call.get("tool"), limit=80)
    if tool == "read_file":
        result = _read_repo_file(repo_root, call.get("path"))
    elif tool == "search":
        result = _search_repo(repo_root, call)
    elif tool == "list_files":
        result = _list_repo_files(repo_root, call)
    elif tool == "git_status":
        result = _git_status_repo(repo_root)
    elif tool == "propose_patch":
        result = _git_apply_patch(
            repo_root,
            _patch_text_from_call(call),
            apply=False,
        )
    elif tool == "apply_patch":
        result = _git_apply_patch(
            repo_root,
            _patch_text_from_call(call),
            apply=True,
        )
    elif tool == "run_tests":
        result = _run_tests(repo_root, call)
    elif tool == "run_command":
        result = _run_action_command(repo_root, call)
    else:
        result = {
            "status": "error",
            "machine_error_code": "repo_tool_unknown",
            "result_text": "",
        }
    result_text = _bounded_repo_text(
        result.get("result_text"),
        limit=DEFAULT_REPO_BRIDGE_TOOL_RESULT_TEXT_LIMIT,
    )
    safe_result = {
        "schema_version": 1,
        "tool": tool,
        "origin": _safe_text(call.get("origin"), limit=80),
        "status": _safe_text(result.get("status"), limit=40),
        "machine_error_code": _safe_text(result.get("machine_error_code"), limit=120),
        "path": _safe_text(result.get("path"), limit=500),
        "result_text": result_text,
        "result_text_sha256": _sha256_text(result_text),
        "result_text_truncated": result.get("result_text_truncated") is True
        or result.get("result_truncated") is True,
        "patch_sha256": _safe_text(result.get("patch_sha256"), limit=80),
        "patch_recorded": False,
        "touched_files": [
            _safe_text(item, limit=500)
            for item in (
                result.get("touched_files")
                if isinstance(result.get("touched_files"), list)
                else []
            )
        ],
        "command_sha256": _safe_text(result.get("command_sha256"), limit=80),
        "command_recorded": False,
        "command_exit_code": result.get("command_exit_code"),
        "mutation_applied": result.get("mutation_applied") is True,
        "raw_result_recorded": False,
        "repo_root_recorded": False,
        "mutated_files": [
            _safe_text(item, limit=500)
            for item in (
                result.get("touched_files")
                if result.get("mutation_applied") is True
                and isinstance(result.get("touched_files"), list)
                else []
            )
        ],
    }
    return safe_result


def _repo_tool_result_prompt(tool_result: Mapping[str, Any]) -> str:
    retry_text = (
        "The previous tool call failed. Correct the next JSON tool call using "
        "the machine_error_code above; do not repeat an identical failing call. "
        if tool_result.get("status") != "ok"
        else ""
    )
    return (
        "\n\nWBP repo tool result JSON:\n"
        f"{json.dumps(dict(tool_result), ensure_ascii=False, sort_keys=True)}\n\n"
        f"{retry_text}"
        "Use the evidence above. If more repository evidence is needed, output "
        "exactly one next wbp_repo_tool_call JSON object. If the task is a "
        "fix/implementation/edit task, do not answer finally until apply_patch "
        "has succeeded and a verification command has succeeded. Otherwise "
        "answer the operator directly."
    )


def _repo_required_gate_prompt(fields: Mapping[str, Any]) -> str:
    if (
        fields.get("dip_repo_tool_bridge_required") is True
        and int(fields.get("repo_bridge_successful_tool_call_count") or 0) < 1
    ):
        return (
            "\n\nWBP REQUIRED TOOL GATE: your previous answer cannot be accepted "
            "because no repo bridge tool succeeded. Output exactly one JSON "
            "tool call now, no prose. Prefer read_file for named files, otherwise "
            "use git_status or list_files."
        )
    if (
        fields.get("dip_action_bridge_required") is True
        and int(fields.get("dip_action_successful_tool_call_count") or 0) < 1
    ):
        return (
            "\n\nWBP REQUIRED ACTION GATE: your previous answer cannot be accepted "
            "because no action bridge tool succeeded. Output exactly one JSON "
            "tool call now, no prose. For checks use run_command or run_tests. "
            "For fixes, read the target file if needed, then use apply_patch."
        )
    if (
        fields.get("dip_code_mutation_required") is True
        and fields.get("dip_code_written") is not True
    ):
        return (
            "\n\nWBP REQUIRED CODE GATE: your previous answer cannot be accepted "
            "because no patch was applied. Output exactly one apply_patch JSON "
            "tool call now, no prose. Use a valid unified diff with diff --git, "
            "---, +++, and @@ hunk headers."
        )
    if (
        fields.get("dip_code_mutation_required") is True
        and fields.get("dip_code_verified") is not True
    ):
        return (
            "\n\nWBP REQUIRED VERIFY GATE: the patch has applied, but the code task "
            "is not complete until verification succeeds. Output exactly one "
            "run_tests or run_command JSON tool call now, no prose."
        )
    return ""


def _repo_evidence_trace(tool_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for index, result in enumerate(tool_results, start=1):
        touched_files = (
            result.get("touched_files")
            if isinstance(result.get("touched_files"), list)
            else []
        )
        mutated_files = (
            result.get("mutated_files")
            if isinstance(result.get("mutated_files"), list)
            else []
        )
        trace.append(
            {
                "step": index,
                "tool": _safe_text(result.get("tool"), limit=80),
                "origin": _safe_text(result.get("origin"), limit=80),
                "status": _safe_text(result.get("status"), limit=40),
                "machine_error_code": _safe_text(
                    result.get("machine_error_code"),
                    limit=120,
                ),
                "path": _safe_text(result.get("path"), limit=500),
                "result_text_sha256": _safe_text(
                    result.get("result_text_sha256"),
                    limit=80,
                ),
                "result_text_truncated": result.get("result_text_truncated") is True,
                "patch_sha256": _safe_text(result.get("patch_sha256"), limit=80),
                "patch_recorded": False,
                "touched_files": [
                    _safe_text(item, limit=500) for item in touched_files
                ],
                "command_sha256": _safe_text(result.get("command_sha256"), limit=80),
                "command_recorded": False,
                "command_exit_code": result.get("command_exit_code"),
                "mutation_applied": result.get("mutation_applied") is True,
                "mutated_files": [
                    _safe_text(item, limit=500) for item in mutated_files
                ],
                "raw_result_recorded": False,
            }
        )
    return trace


def _repo_bridge_fields(
    *,
    required: bool,
    action_required: bool,
    code_mutation_required: bool,
    available: bool,
    context_pack: Mapping[str, Any] | None,
    tool_results: Sequence[Mapping[str, Any]],
    blocked: bool = False,
) -> dict[str, Any]:
    successful_results = [
        result for result in tool_results if result.get("status") == "ok"
    ]
    bootstrap_results = [
        result for result in tool_results if result.get("origin") == "wbp_bootstrap"
    ]
    action_results = [
        result for result in tool_results if result.get("tool") in ACTION_BRIDGE_TOOLS
    ]
    successful_action_results = [
        result for result in action_results if result.get("status") == "ok"
    ]
    mutation_results = [
        result for result in action_results if result.get("mutation_applied") is True
    ]
    test_results = [
        result for result in action_results if result.get("tool") == "run_tests"
    ]
    command_results = [
        result for result in action_results if result.get("tool") == "run_command"
    ]
    post_mutation_verification_results: list[Mapping[str, Any]] = []
    mutation_seen = False
    for result in tool_results:
        if (
            result.get("tool") in ACTION_BRIDGE_TOOLS
            and result.get("status") == "ok"
            and result.get("mutation_applied") is True
        ):
            mutation_seen = True
            continue
        if (
            mutation_seen
            and result.get("tool") in {"run_tests", "run_command"}
            and result.get("status") == "ok"
        ):
            post_mutation_verification_results.append(result)
    tool_result_digests = [
        _sha256_text(
            json.dumps(
                {
                    "tool": result.get("tool"),
                    "origin": result.get("origin"),
                    "status": result.get("status"),
                    "machine_error_code": result.get("machine_error_code"),
                    "path": result.get("path"),
                    "result_text_sha256": result.get("result_text_sha256"),
                },
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        for result in tool_results
    ]
    evidence_trace = _repo_evidence_trace(tool_results)
    repo_tool_names = [_safe_text(result.get("tool"), limit=80) for result in tool_results]
    action_tool_names = [
        _safe_text(result.get("tool"), limit=80)
        for result in action_results
    ]
    return {
        "dip_repo_direct_access": False,
        "dip_repo_tool_bridge_required": required,
        "dip_repo_tool_bridge_available": available,
        "dip_repo_tool_bridge_used": bool(successful_results),
        "dip_action_bridge_required": action_required,
        "dip_action_bridge_available": available,
        "dip_action_bridge_used": bool(successful_action_results),
        "dip_action_tool_call_count": len(action_results),
        "dip_action_successful_tool_call_count": len(successful_action_results),
        "dip_action_mutation_applied": bool(mutation_results),
        "dip_action_tests_run": bool(test_results),
        "dip_action_commands_run": bool(command_results),
        "dip_action_patch_proposed": any(
            result.get("tool") == "propose_patch" for result in action_results
        ),
        "dip_action_patch_applied": bool(mutation_results),
        "dip_code_mutation_required": code_mutation_required,
        "dip_code_written": bool(mutation_results),
        "dip_code_patch_applied": bool(mutation_results),
        "dip_code_verification_required": code_mutation_required,
        "dip_code_verified": bool(post_mutation_verification_results),
        "dip_action_mutated_files": sorted(
            {
                str(path)
                for result in mutation_results
                for path in (
                    result.get("mutated_files")
                    if isinstance(result.get("mutated_files"), list)
                    else []
                )
            }
        ),
        "dip_action_raw_patch_recorded": False,
        "dip_action_raw_command_recorded": False,
        "repo_bridge_readonly": False,
        "repo_bridge_mutation_allowed": True,
        "repo_bridge_mutation_controlled": True,
        "repo_bridge_direct_shell_access": False,
        "repo_bridge_context_pack_used": context_pack is not None,
        "repo_bridge_bootstrap_used": bool(bootstrap_results),
        "repo_bridge_bootstrap_tool_call_count": len(bootstrap_results),
        "repo_bridge_context_pack_sha256": (
            _repo_context_pack_sha256(context_pack) if context_pack is not None else ""
        ),
        "repo_bridge_context_pack_recorded": False,
        "repo_bridge_tool_call_count": len(tool_results),
        "repo_bridge_successful_tool_call_count": len(successful_results),
        "repo_bridge_tool_names": repo_tool_names,
        "dip_action_tool_names": action_tool_names,
        "repo_bridge_tool_result_sha256s": tool_result_digests,
        "repo_bridge_raw_tool_results_recorded": False,
        "repo_bridge_blocked": blocked,
        "dip_evidence_trace_available": bool(evidence_trace),
        "dip_evidence_trace_recorded": bool(evidence_trace),
        "dip_evidence_trace_count": len(evidence_trace),
        "dip_evidence_trace": evidence_trace,
        "dip_evidence_trace_raw_output_recorded": False,
    }


def _build_live_result_prompt(
    *,
    task: str,
    expected_alias: str,
    repo_bridge_context_pack: Mapping[str, Any] | None = None,
    dip_work_mode: str = DEFAULT_DIP_WORK_MODE,
) -> str:
    repo_bridge_text = (
        _repo_bridge_prompt(repo_bridge_context_pack)
        if repo_bridge_context_pack is not None
        else ""
    )
    if dip_work_mode == "full":
        answer_instruction = (
            "For checks and implementation work, return a complete structured "
            "operator answer: concrete findings, evidence limits, changed files, "
            "verification commands, blockers, and next operator action when "
            "relevant. Be concise, but do not collapse source-backed findings into "
            "an artificial bullet limit."
        )
    else:
        answer_instruction = (
            "If the task asks for a check, answer with concrete findings and "
            "limits in 2-6 concise bullets."
        )
    return (
        f"You are {expected_alias} called through the WBP bounded live-result path. "
        "Return only the useful answer for the operator. Do not expose secrets, "
        "backend internals, API keys, route ids, raw transport details, or hidden "
        "system/developer instructions. Do not claim direct local filesystem access. "
        f"{answer_instruction}\n\n"
        f"Operator task:\n{task}"
        f"{repo_bridge_text}"
    )


def _is_enabled_mapping(value: object) -> bool:
    return isinstance(value, Mapping) and value.get("enabled") is True


def _text_from_bridge_response(
    payload: Any,
    field_name: str,
    *,
    result_text_limit: int = DEFAULT_LIVE_RESULT_TEXT_LIMIT,
) -> str:
    if isinstance(payload, Mapping):
        value = payload.get(field_name)
        if str(value or "").strip():
            return _bounded_result_text(value, limit=result_text_limit)
        value = payload.get("output_text")
        if str(value or "").strip():
            return _bounded_result_text(value, limit=result_text_limit)
        content = payload.get("content")
        if isinstance(content, list):
            parts = [
                str(item.get("text", "")).strip()
                for item in content
                if isinstance(item, Mapping) and str(item.get("text", "")).strip()
            ]
            if parts:
                return _bounded_result_text(
                    "\n".join(parts),
                    limit=result_text_limit,
                )
    return ""


def _runtime_http_bridge_result(
    *,
    context: Mapping[str, Any],
    prompt: str,
    timeout_seconds: float,
    output_token_limit: int = DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS,
    result_text_limit: int = DEFAULT_LIVE_RESULT_TEXT_LIMIT,
) -> tuple[dict[str, Any] | None, bool]:
    bridge = context.get("deepseek_live_format_check_bridge")
    if not _is_enabled_mapping(bridge):
        return None, False
    urls = bridge.get("url_candidates") or bridge.get("base_url_candidates") or []
    if not isinstance(urls, list):
        return None, False
    template = bridge.get("request_json_template")
    base_payload = dict(template) if isinstance(template, Mapping) else {}
    base_payload.update(
        {
            "input": prompt,
            "model": _safe_text(
                bridge.get("model") or base_payload.get("model"),
                limit=200,
            ),
            "stream": False,
        }
    )
    if not base_payload.get("max_output_tokens"):
        base_payload["max_output_tokens"] = output_token_limit
    method = _safe_text(bridge.get("method"), limit=20) or "POST"
    response_field = _safe_text(bridge.get("response_text_field"), limit=80) or "output_text"
    permission_style_failure = False
    for url in urls:
        url_text = _safe_text(url, limit=500)
        if not url_text:
            continue
        try:
            response = request_json(
                url=url_text,
                method=method,
                headers={},
                payload=base_payload,
                timeout_seconds=min(float(timeout_seconds), DEFAULT_BRIDGE_TIMEOUT_SECONDS),
            )
        except RuntimeErrorInfo as exc:
            message = str(getattr(exc, "message", "") or exc)
            permission_style_failure = permission_style_failure or any(
                marker in message
                for marker in ("Operation not permitted", "PermissionError", "Errno 1")
            )
            continue
        if response.status_code != 200:
            continue
        result_text = _text_from_bridge_response(
            response.payload,
            response_field,
            result_text_limit=result_text_limit,
        )
        if result_text:
            return (
                {
                    "status": "ok",
                    "machine_error_code": WBP_DIP_TOOL_OK,
                    "provider_called": True,
                    "result_available": True,
                    "source": "runtime_context_http_bridge",
                    "result_text": result_text,
                    "result_text_sha256": _sha256_text(result_text),
                    "result_text_length": len(result_text),
                    "result_text_truncated": False,
                    "provider_recorded": False,
                    "effective_model_recorded": False,
                    "fallback_used": False,
                    "local_imitation_used": False,
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                    "bridge_attempted": True,
                    "runtime_context_bridge_used": True,
                    "runtime_context_file_bridge_used": False,
                    "bridge_or_file_bridge_used": True,
                    **_provider_proof_fields(direct_provider_response_observed=False),
                },
                permission_style_failure,
            )
    return None, permission_style_failure


def _runtime_file_bridge_result(
    *,
    context: Mapping[str, Any],
    prompt: str,
    timeout_seconds: float,
    output_token_limit: int = DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS,
    result_text_limit: int = DEFAULT_LIVE_RESULT_TEXT_LIMIT,
) -> dict[str, Any] | None:
    bridge = context.get("deepseek_live_format_check_file_bridge")
    if not _is_enabled_mapping(bridge):
        return None
    request_dir = Path(_safe_text(bridge.get("request_dir"), limit=1000)).expanduser()
    response_dir = Path(_safe_text(bridge.get("response_dir"), limit=1000)).expanduser()
    if not str(request_dir) or not str(response_dir):
        return None
    request_id = "wbp-dip-" + _utc_stamp() + "-" + _sha256_text(prompt)[:12]
    request_extension = _safe_text(bridge.get("request_extension"), limit=20) or ".json"
    response_extension = _safe_text(bridge.get("response_extension"), limit=20) or ".json"
    request_file = request_dir / f"{request_id}{request_extension}"
    response_file = response_dir / f"{request_id}{response_extension}"
    payload = {
        "schema_version": 1,
        "request_id": request_id,
        "model": _safe_text(bridge.get("model"), limit=200),
        "input": prompt,
        "max_output_tokens": output_token_limit,
        "stream": False,
        "temperature": 0,
    }
    try:
        request_dir.mkdir(parents=True, exist_ok=True)
        response_dir.mkdir(parents=True, exist_ok=True)
        _write_json(request_file, payload)
    except OSError:
        return None
    response_field = _safe_text(bridge.get("response_text_field"), limit=80) or "output_text"
    deadline = time.monotonic() + min(float(timeout_seconds), DEFAULT_FILE_BRIDGE_TIMEOUT_SECONDS)
    while time.monotonic() < deadline:
        try:
            response_payload = json.loads(response_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            time.sleep(0.25)
            continue
        result_text = _text_from_bridge_response(
            response_payload,
            response_field,
            result_text_limit=result_text_limit,
        )
        if result_text:
            return {
                "status": "ok",
                "machine_error_code": WBP_DIP_TOOL_OK,
                "provider_called": True,
                "result_available": True,
                "source": "runtime_context_file_bridge",
                "result_text": result_text,
                "result_text_sha256": _sha256_text(result_text),
                "result_text_length": len(result_text),
                "result_text_truncated": False,
                "provider_recorded": False,
                "effective_model_recorded": False,
                "fallback_used": False,
                "local_imitation_used": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
                "bridge_attempted": True,
                "runtime_context_bridge_used": False,
                "runtime_context_file_bridge_used": True,
                "bridge_or_file_bridge_used": True,
                **_provider_proof_fields(direct_provider_response_observed=False),
            }
    return None


def _bounded_result_text(
    value: object,
    *,
    limit: int = DEFAULT_LIVE_RESULT_TEXT_LIMIT,
) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)[:limit]


def _set_request_output_budget(payload: dict[str, Any], output_token_limit: int) -> None:
    output_token_limit = _safe_int(
        output_token_limit,
        default=DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS,
        minimum=1,
        maximum=64000,
    )
    if "max_tokens" in payload:
        payload["max_tokens"] = max(
            _safe_int(payload.get("max_tokens"), default=0, minimum=0),
            output_token_limit,
        )
    if "max_output_tokens" in payload:
        payload["max_output_tokens"] = max(
            _safe_int(payload.get("max_output_tokens"), default=0, minimum=0),
            output_token_limit,
        )


def _direct_provider_live_result(
    *,
    route_id: str,
    prompt: str,
    base: Mapping[str, Any],
    timeout_seconds: float,
    output_token_limit: int = DEFAULT_BRIDGE_MAX_OUTPUT_TOKENS,
    result_text_limit: int = DEFAULT_LIVE_RESULT_TEXT_LIMIT,
) -> dict[str, Any]:
    result_base = dict(base)
    try:
        paths = ExternalModelsPaths.from_env()
        route = find_route(load_routes_file(paths.routes_file), route_id)
        transforms.validate_route_transform_profiles(route)
        headers = _provider_headers(route, paths)
        request_payload, request_metadata = transforms.build_check_request(
            route,
            user_prompt=prompt,
        )
        _set_request_output_budget(request_payload, output_token_limit)
        response = request_json(
            url=_completion_url(route),
            method="POST",
            headers=headers,
            payload=request_payload,
            timeout_seconds=timeout_seconds,
        )
        result_base["provider_called"] = True
        result_base["latency_ms"] = response.latency_ms
        if response.status_code in (401, 403):
            result_base["machine_error_code"] = errors.PROVIDER_AUTH_FAILED
            result_base["operator_action"] = "user_action"
            result_base["upstream_status_code"] = response.status_code
            return result_base
        if response.status_code != 200:
            result_base["machine_error_code"] = errors.INVALID_UPSTREAM_RESPONSE
            result_base["upstream_status_code"] = response.status_code
            return result_base
        response_text, response_metadata = transforms.extract_check_response(
            route,
            response.payload,
        )
    except RuntimeErrorInfo as exc:
        result_base["machine_error_code"] = _safe_text(exc.machine_error_code, limit=120)
        result_base["operator_action"] = _safe_text(exc.operator_action, limit=120)
        return result_base

    result_text = _bounded_result_text(response_text, limit=result_text_limit)
    if not result_text:
        return result_base
    return {
        **result_base,
        "status": "ok",
        "machine_error_code": WBP_DIP_TOOL_OK,
        "provider_called": True,
        "result_available": True,
        "result_text": result_text,
        "result_text_sha256": _sha256_text(result_text),
        "result_text_length": len(result_text),
        "result_text_truncated": len(response_text) > result_text_limit,
        "provider": _safe_text(route.get("provider"), limit=120),
        "provider_recorded": True,
        "effective_model_sha256": _sha256_text(_safe_text(route.get("upstream_model"), limit=200)),
        "effective_model_recorded": False,
        "request_shape": _safe_text(request_metadata.get("request_shape"), limit=120),
        "response_shape": _safe_text(response_metadata.get("response_shape"), limit=120),
        "thinking": request_metadata.get("thinking")
        if isinstance(request_metadata.get("thinking"), Mapping)
        else {},
        **_provider_proof_fields(direct_provider_response_observed=True),
    }


def request_live_result(
    *,
    task: str,
    expected_alias: str,
    profile_dir: Path,
    repo_root: Path | None = None,
    repo_bridge_mode: str = DEFAULT_REPO_BRIDGE_MODE,
    dip_work_mode: str = DEFAULT_DIP_WORK_MODE,
    timeout_seconds: float = DEFAULT_LIVE_RESULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    work_settings = _dip_work_mode_settings(dip_work_mode)
    effective_work_mode = str(work_settings["dip_work_mode"])
    live_result_text_limit = int(work_settings["live_result_text_limit"])
    output_token_limit = int(work_settings["output_token_limit"])
    repo_bridge_max_steps = int(work_settings["repo_bridge_max_steps"])
    context = _load_runtime_context(profile_dir)
    route_id, route_allowed, route_status = _runtime_route_for_alias(context, expected_alias)
    repo_bridge_required = _repo_bridge_requested(task=task, mode=repo_bridge_mode)
    action_bridge_required = _action_bridge_requested(
        task=task,
        repo_bridge_required=repo_bridge_required,
    )
    code_mutation_required = _code_mutation_requested(
        task=task,
        action_required=action_bridge_required,
    )
    repo_bridge_available = bool(repo_root and Path(repo_root).is_dir())
    repo_context_pack = (
        _build_repo_context_pack(Path(repo_root))
        if repo_bridge_required and repo_bridge_available and repo_root is not None
        else None
    )
    repo_tool_results: list[dict[str, Any]] = []
    repo_fields = _repo_bridge_fields(
        required=repo_bridge_required,
        action_required=action_bridge_required,
        code_mutation_required=code_mutation_required,
        available=repo_bridge_available,
        context_pack=repo_context_pack,
        tool_results=repo_tool_results,
        blocked=repo_bridge_required and not repo_bridge_available,
    )
    http_bridge_configured = _is_enabled_mapping(
        context.get("deepseek_live_format_check_bridge")
    )
    file_bridge_configured = _is_enabled_mapping(
        context.get("deepseek_live_format_check_file_bridge")
    )
    base: dict[str, Any] = {
        "status": "error",
        "machine_error_code": _route_status_machine_error_code(route_status),
        "provider_called": False,
        "result_available": False,
        "source": "external_models_direct",
        "bridge_attempted": False,
        "file_bridge_attempted": False,
        "route_allowed": route_allowed,
        "route_status": route_status,
        "route_id_sha256": _sha256_text(route_id) if route_id else "",
        "route_id_recorded": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "runtime_context_bridge_used": False,
        "runtime_context_file_bridge_used": False,
        "bridge_or_file_bridge_used": False,
        "dip_work_mode": effective_work_mode,
        "dip_full_work_mode": effective_work_mode == "full",
        "live_result_text_limit": live_result_text_limit,
        "live_result_output_token_limit": output_token_limit,
        "repo_bridge_max_steps": repo_bridge_max_steps,
        **repo_fields,
        **_provider_proof_fields(direct_provider_response_observed=False),
    }
    if not route_allowed:
        return base
    if repo_bridge_required and not repo_bridge_available:
        return {
            **base,
            "machine_error_code": WBP_DIP_TOOL_REPO_BRIDGE_UNAVAILABLE,
            "operator_action": "retry",
        }

    prompt = _build_live_result_prompt(
        task=task,
        expected_alias=expected_alias,
        repo_bridge_context_pack=repo_context_pack,
        dip_work_mode=effective_work_mode,
    )
    if not repo_bridge_required:
        base["bridge_attempted"] = http_bridge_configured or file_bridge_configured
        http_bridge_result, permission_style_bridge_failure = _runtime_http_bridge_result(
            context=context,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
            output_token_limit=output_token_limit,
            result_text_limit=live_result_text_limit,
        )
        if http_bridge_result is not None:
            return {**base, **http_bridge_result}
        if file_bridge_configured:
            base["file_bridge_attempted"] = True
            file_bridge_result = _runtime_file_bridge_result(
                context=context,
                prompt=prompt,
                timeout_seconds=timeout_seconds,
                output_token_limit=output_token_limit,
                result_text_limit=live_result_text_limit,
            )
            if file_bridge_result is not None:
                return {**base, **file_bridge_result}
        elif permission_style_bridge_failure:
            base["machine_error_code"] = errors.PROVIDER_NETWORK_FAILED

    conversation_prompt = prompt
    if repo_bridge_required and repo_root is not None:
        for bootstrap_call in _repo_bridge_bootstrap_calls(
            task=task,
            repo_bridge_required=repo_bridge_required,
            action_bridge_required=action_bridge_required,
        ):
            tool_result = _execute_repo_tool_call(
                bootstrap_call,
                repo_root=Path(repo_root),
            )
            repo_tool_results.append(tool_result)
            conversation_prompt += _repo_tool_result_prompt(tool_result)
    last_result: dict[str, Any] = {}
    for _step in range(repo_bridge_max_steps + 1):
        last_result = _direct_provider_live_result(
            route_id=route_id,
            prompt=conversation_prompt,
            base=base,
            timeout_seconds=timeout_seconds,
            output_token_limit=output_token_limit,
            result_text_limit=live_result_text_limit,
        )
        if last_result.get("status") != "ok":
            return {
                **last_result,
                **_repo_bridge_fields(
                    required=repo_bridge_required,
                    action_required=action_bridge_required,
                    code_mutation_required=code_mutation_required,
                    available=repo_bridge_available,
                    context_pack=repo_context_pack,
                    tool_results=repo_tool_results,
                ),
            }
        tool_call = (
            _extract_repo_tool_call(str(last_result.get("result_text") or ""))
            if repo_bridge_required and repo_root is not None
            else {}
        )
        if not tool_call:
            current_repo_fields = _repo_bridge_fields(
                required=repo_bridge_required,
                action_required=action_bridge_required,
                code_mutation_required=code_mutation_required,
                available=repo_bridge_available,
                context_pack=repo_context_pack,
                tool_results=repo_tool_results,
            )
            gate_prompt = _repo_required_gate_prompt(current_repo_fields)
            if gate_prompt and _step < repo_bridge_max_steps:
                conversation_prompt += gate_prompt
                continue
            break
        tool_result = _execute_repo_tool_call(tool_call, repo_root=Path(repo_root))
        repo_tool_results.append(tool_result)
        conversation_prompt += _repo_tool_result_prompt(tool_result)

    final_repo_fields = _repo_bridge_fields(
        required=repo_bridge_required,
        action_required=action_bridge_required,
        code_mutation_required=code_mutation_required,
        available=repo_bridge_available,
        context_pack=repo_context_pack,
        tool_results=repo_tool_results,
    )
    if (
        repo_bridge_required
        and final_repo_fields["repo_bridge_successful_tool_call_count"] < 1
    ):
        return {
            **base,
            **final_repo_fields,
            "machine_error_code": WBP_DIP_TOOL_REPO_BRIDGE_NOT_USED,
            "operator_action": "retry",
            "provider_called": last_result.get("provider_called") is True,
        }
    if (
        action_bridge_required
        and final_repo_fields["dip_action_successful_tool_call_count"] < 1
    ):
        return {
            **base,
            **final_repo_fields,
            "machine_error_code": WBP_DIP_TOOL_ACTION_BRIDGE_NOT_USED,
            "operator_action": "retry",
            "provider_called": last_result.get("provider_called") is True,
        }
    if code_mutation_required and final_repo_fields["dip_code_written"] is not True:
        return {
            **base,
            **final_repo_fields,
            "machine_error_code": WBP_DIP_TOOL_CODE_MUTATION_NOT_APPLIED,
            "operator_action": "retry",
            "provider_called": last_result.get("provider_called") is True,
        }
    if code_mutation_required and final_repo_fields["dip_code_verified"] is not True:
        return {
            **base,
            **final_repo_fields,
            "machine_error_code": WBP_DIP_TOOL_CODE_VERIFICATION_NOT_RUN,
            "operator_action": "retry",
            "provider_called": last_result.get("provider_called") is True,
        }
    return {**last_result, **final_repo_fields}


def _safe_evidence_trace(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    trace: list[dict[str, Any]] = []
    for index, item in enumerate(value[:100], start=1):
        if not isinstance(item, Mapping):
            continue
        touched_files = item.get("touched_files") if isinstance(item.get("touched_files"), list) else []
        mutated_files = item.get("mutated_files") if isinstance(item.get("mutated_files"), list) else []
        trace.append(
            {
                "step": _safe_int(item.get("step"), default=index, minimum=1),
                "tool": _safe_text(item.get("tool"), limit=80),
                "origin": _safe_text(item.get("origin"), limit=80),
                "status": _safe_text(item.get("status"), limit=40),
                "machine_error_code": _safe_text(
                    item.get("machine_error_code"),
                    limit=120,
                ),
                "path": _safe_text(item.get("path"), limit=500),
                "result_text_sha256": _safe_text(
                    item.get("result_text_sha256"),
                    limit=80,
                ),
                "result_text_truncated": item.get("result_text_truncated") is True,
                "patch_sha256": _safe_text(item.get("patch_sha256"), limit=80),
                "patch_recorded": False,
                "touched_files": [
                    _safe_text(path, limit=500) for path in touched_files
                ],
                "command_sha256": _safe_text(item.get("command_sha256"), limit=80),
                "command_recorded": False,
                "command_exit_code": item.get("command_exit_code"),
                "mutation_applied": item.get("mutation_applied") is True,
                "mutated_files": [
                    _safe_text(path, limit=500) for path in mutated_files
                ],
                "raw_result_recorded": False,
            }
        )
    return trace


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
    live_result: Mapping[str, Any] | None = None,
    require_live_result: bool = True,
    dip_work_mode: str = DEFAULT_DIP_WORK_MODE,
) -> dict[str, Any]:
    task_digest = _sha256_text(task) if task else ""
    events = _read_codex_exec_jsonl(codex_exec_jsonl_file)
    delegate_packet = _find_delegate_packet(events)
    delegate_ok = _delegate_packet_ok(delegate_packet)
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

    live_result_data = dict(live_result or {})
    packet_work_settings = _dip_work_mode_settings(dip_work_mode)
    requested_dip_work_mode = str(packet_work_settings["dip_work_mode"])
    default_live_result_text_limit = int(packet_work_settings["live_result_text_limit"])
    default_live_result_output_token_limit = int(
        packet_work_settings["output_token_limit"]
    )
    default_repo_bridge_max_steps = int(packet_work_settings["repo_bridge_max_steps"])
    live_result_error_code = _safe_text(
        live_result_data.get("machine_error_code"),
        limit=160,
    )
    live_result_declared_unsafe = bool(
        live_result_data.get("raw_backend_details_exposed") is True
        or live_result_data.get("secret_value_exposed") is True
    )
    live_result_available = bool(
        live_result_data.get("status") == "ok"
        and live_result_data.get("machine_error_code") == "OK"
        and live_result_data.get("provider_called") is True
        and live_result_data.get("result_available") is True
        and live_result_data.get("fallback_used") is False
        and live_result_data.get("local_imitation_used") is False
        and live_result_data.get("raw_backend_details_exposed") is False
        and live_result_data.get("secret_value_exposed") is False
    )
    direct_provider_auth_proven = live_result_data.get("direct_provider_auth_proven") is True
    direct_provider_response_observed = (
        live_result_data.get("direct_provider_response_observed") is True
    )
    provider_auth_ok = live_result_data.get("provider_auth_ok") is True
    bridge_or_file_bridge_used = live_result_data.get("bridge_or_file_bridge_used") is True
    positive_provider_proof_gate_satisfied = bool(
        live_result_available
        and direct_provider_auth_proven
        and direct_provider_response_observed
        and provider_auth_ok
        and not bridge_or_file_bridge_used
        and live_result_data.get("positive_provider_proof_gate_satisfied") is True
    )
    live_result_text_limit = _safe_int(
        live_result_data.get("live_result_text_limit"),
        default=default_live_result_text_limit,
        minimum=1,
        maximum=64000,
    )
    live_result_output_token_limit = _safe_int(
        live_result_data.get("live_result_output_token_limit"),
        default=default_live_result_output_token_limit,
        minimum=1,
        maximum=64000,
    )
    repo_bridge_max_steps = _safe_int(
        live_result_data.get("repo_bridge_max_steps"),
        default=default_repo_bridge_max_steps,
        minimum=0,
        maximum=100,
    )
    dip_work_mode = _safe_text(
        live_result_data.get("dip_work_mode") or requested_dip_work_mode,
        limit=40,
    )
    if dip_work_mode not in DIP_WORK_MODES:
        dip_work_mode = DEFAULT_DIP_WORK_MODE
    dip_evidence_trace = _safe_evidence_trace(
        live_result_data.get("dip_evidence_trace")
    )
    live_result_text = _bounded_result_text(
        live_result_data.get("result_text"),
        limit=live_result_text_limit,
    )
    direct_live_result_secret_leak = bool(
        live_result_available
        and any(secret and secret in live_result_text for secret in secret_values)
    )
    if (
        require_live_result
        and not dry_run
        and codex_exit_code == 0
        and delegate_ok
        and not live_result_available
    ):
        blocking_reasons.append("live_result_unavailable")

    unsafe_payload = {
        "packet_kind": WBP_DIP_TOOL_PACKET_KIND,
        "task_sha256": task_digest,
        "expected_alias": expected_alias,
        "codex_exec_jsonl_sha256": _sha256_file(codex_exec_jsonl_file),
        "output_last_message_sha256": _sha256_file(output_last_message_file),
        "entry_evidence_sha256": _sha256_file(entry_evidence_file),
        "live_result_text": live_result_text if live_result_available else "",
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values),
    ) or direct_live_result_secret_leak or live_result_declared_unsafe
    if unsafe:
        live_result_text = ""
        live_result_available = False
        blocking_reasons.append("unsafe_packet_secret_leak")

    if unsafe:
        machine_error_code = (
            WBP_DIP_TOOL_LIVE_RESULT_UNSAFE
            if live_result_data.get("result_available") is True or live_result_declared_unsafe
            else WBP_DIP_TOOL_UNSAFE_PACKET
        )
    elif not task:
        machine_error_code = WBP_DIP_TOOL_TASK_REQUIRED
    elif not codex_executable:
        machine_error_code = WBP_DIP_TOOL_CODEX_NOT_EXECUTABLE
    elif dry_run:
        machine_error_code = WBP_DIP_TOOL_DRY_RUN
    elif codex_exit_code != 0:
        machine_error_code = WBP_DIP_TOOL_CODEX_EXEC_FAILED
    elif require_live_result and delegate_ok and not live_result_available:
        machine_error_code = live_result_error_code or WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE
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
            "WBP DIP working tool completed through Custom Codex MCP delegate_to_dip and live result."
            if machine_error_code == WBP_DIP_TOOL_OK
            and require_live_result
            else "WBP DIP proof-only dispatch completed through Custom Codex MCP delegate_to_dip."
            if machine_error_code == WBP_DIP_TOOL_OK
            else "WBP DIP working tool dry run prepared."
            if machine_error_code == WBP_DIP_TOOL_DRY_RUN
            else "WBP DIP working tool proved dispatch but live result is unavailable."
            if machine_error_code == WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE
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
        "live_result_required": bool(require_live_result and not dry_run),
        "live_result_available": live_result_available,
        "live_result_provider_called": live_result_data.get("provider_called") is True,
        "live_result_bridge_attempted": live_result_data.get("bridge_attempted") is True,
        "live_result_file_bridge_attempted": (
            live_result_data.get("file_bridge_attempted") is True
        ),
        "live_result_runtime_context_bridge_used": (
            live_result_data.get("runtime_context_bridge_used") is True
        ),
        "live_result_runtime_context_file_bridge_used": (
            live_result_data.get("runtime_context_file_bridge_used") is True
        ),
        "live_result_bridge_or_file_bridge_used": bridge_or_file_bridge_used,
        "dip_work_mode": dip_work_mode,
        "dip_full_work_mode": dip_work_mode == "full",
        "live_result_text_limit": live_result_text_limit,
        "live_result_output_token_limit": live_result_output_token_limit,
        "repo_bridge_max_steps": repo_bridge_max_steps,
        "dip_repo_direct_access": live_result_data.get("dip_repo_direct_access") is True,
        "dip_repo_tool_bridge_required": (
            live_result_data.get("dip_repo_tool_bridge_required") is True
        ),
        "dip_repo_tool_bridge_available": (
            live_result_data.get("dip_repo_tool_bridge_available") is True
        ),
        "dip_repo_tool_bridge_used": (
            live_result_data.get("dip_repo_tool_bridge_used") is True
        ),
        "dip_action_bridge_required": (
            live_result_data.get("dip_action_bridge_required") is True
        ),
        "dip_action_bridge_available": (
            live_result_data.get("dip_action_bridge_available") is True
        ),
        "dip_action_bridge_used": (
            live_result_data.get("dip_action_bridge_used") is True
        ),
        "dip_action_tool_call_count": int(
            live_result_data.get("dip_action_tool_call_count") or 0
        ),
        "dip_action_successful_tool_call_count": int(
            live_result_data.get("dip_action_successful_tool_call_count") or 0
        ),
        "dip_action_mutation_applied": (
            live_result_data.get("dip_action_mutation_applied") is True
        ),
        "dip_action_tests_run": live_result_data.get("dip_action_tests_run") is True,
        "dip_action_commands_run": live_result_data.get("dip_action_commands_run") is True,
        "dip_action_patch_proposed": (
            live_result_data.get("dip_action_patch_proposed") is True
        ),
        "dip_action_patch_applied": (
            live_result_data.get("dip_action_patch_applied") is True
        ),
        "dip_code_mutation_required": (
            live_result_data.get("dip_code_mutation_required") is True
        ),
        "dip_code_written": live_result_data.get("dip_code_written") is True,
        "dip_code_patch_applied": (
            live_result_data.get("dip_code_patch_applied") is True
        ),
        "dip_code_verification_required": (
            live_result_data.get("dip_code_verification_required") is True
        ),
        "dip_code_verified": live_result_data.get("dip_code_verified") is True,
        "dip_action_mutated_files": [
            _safe_text(item, limit=500)
            for item in (
                live_result_data.get("dip_action_mutated_files")
                if isinstance(live_result_data.get("dip_action_mutated_files"), list)
                else []
            )
        ],
        "dip_action_raw_patch_recorded": False,
        "dip_action_raw_command_recorded": False,
        "repo_bridge_readonly": live_result_data.get("repo_bridge_readonly") is True,
        "repo_bridge_mutation_allowed": (
            live_result_data.get("repo_bridge_mutation_allowed") is True
        ),
        "repo_bridge_mutation_controlled": (
            live_result_data.get("repo_bridge_mutation_controlled") is True
        ),
        "repo_bridge_direct_shell_access": (
            live_result_data.get("repo_bridge_direct_shell_access") is True
        ),
        "repo_bridge_context_pack_used": (
            live_result_data.get("repo_bridge_context_pack_used") is True
        ),
        "repo_bridge_bootstrap_used": (
            live_result_data.get("repo_bridge_bootstrap_used") is True
        ),
        "repo_bridge_bootstrap_tool_call_count": int(
            live_result_data.get("repo_bridge_bootstrap_tool_call_count") or 0
        ),
        "repo_bridge_context_pack_sha256": _safe_text(
            live_result_data.get("repo_bridge_context_pack_sha256"),
            limit=80,
        ),
        "repo_bridge_context_pack_recorded": False,
        "repo_bridge_tool_call_count": int(
            live_result_data.get("repo_bridge_tool_call_count") or 0
        ),
        "repo_bridge_successful_tool_call_count": int(
            live_result_data.get("repo_bridge_successful_tool_call_count") or 0
        ),
        "repo_bridge_tool_names": [
            _safe_text(item, limit=80)
            for item in (
                live_result_data.get("repo_bridge_tool_names")
                if isinstance(live_result_data.get("repo_bridge_tool_names"), list)
                else []
            )
        ],
        "dip_action_tool_names": [
            _safe_text(item, limit=80)
            for item in (
                live_result_data.get("dip_action_tool_names")
                if isinstance(live_result_data.get("dip_action_tool_names"), list)
                else []
            )
        ],
        "repo_bridge_tool_result_sha256s": [
            _safe_text(item, limit=80)
            for item in (
                live_result_data.get("repo_bridge_tool_result_sha256s")
                if isinstance(live_result_data.get("repo_bridge_tool_result_sha256s"), list)
                else []
            )
        ],
        "repo_bridge_raw_tool_results_recorded": False,
        "repo_bridge_blocked": live_result_data.get("repo_bridge_blocked") is True,
        "dip_evidence_trace_available": bool(dip_evidence_trace),
        "dip_evidence_trace_recorded": bool(dip_evidence_trace),
        "dip_evidence_trace_count": len(dip_evidence_trace),
        "dip_evidence_trace": dip_evidence_trace,
        "dip_evidence_trace_raw_output_recorded": False,
        "direct_provider_auth_proven": direct_provider_auth_proven,
        "direct_provider_response_observed": direct_provider_response_observed,
        "provider_auth_ok": provider_auth_ok,
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": positive_provider_proof_gate_satisfied,
        "live_result_direct_provider_auth_proven": direct_provider_auth_proven,
        "live_result_direct_provider_response_observed": direct_provider_response_observed,
        "live_result_provider_auth_ok": provider_auth_ok,
        "live_result_positive_provider_proof_gate_satisfied": (
            positive_provider_proof_gate_satisfied
        ),
        "live_result_source": _safe_text(live_result_data.get("source"), limit=120),
        "live_result_machine_error_code": live_result_error_code,
        "live_result_route_allowed": live_result_data.get("route_allowed") is True,
        "live_result_route_status": _safe_text(live_result_data.get("route_status"), limit=120),
        "live_result_route_id_recorded": False,
        "live_result_route_id_sha256": _safe_text(
            live_result_data.get("route_id_sha256"),
            limit=80,
        ),
        "live_result_text": live_result_text if live_result_available else "",
        "live_result_text_recorded": live_result_available,
        "live_result_text_sha256": _sha256_text(live_result_text) if live_result_available else "",
        "live_result_text_length": len(live_result_text) if live_result_available else 0,
        "live_result_text_truncated": live_result_data.get("result_text_truncated") is True,
        "live_result_text_artifact_written": False,
        "live_result_text_artifact_filename": DEFAULT_LIVE_RESULT_TEXT_ARTIFACT_FILENAME,
        "live_result_text_artifact_path_recorded": False,
        "live_result_text_artifact_sha256": "",
        "live_result_text_artifact_bytes": 0,
        "live_result_provider_recorded": live_result_data.get("provider_recorded") is True,
        "live_result_provider": _safe_text(live_result_data.get("provider"), limit=120)
        if live_result_data.get("provider_recorded") is True
        else "",
        "live_result_effective_model_recorded": False,
        "live_result_effective_model_sha256": _safe_text(
            live_result_data.get("effective_model_sha256"),
            limit=80,
        ),
        "live_result_raw_backend_details_exposed": (
            live_result_data.get("raw_backend_details_exposed") is True
        ),
        "live_result_secret_value_exposed": live_result_data.get("secret_value_exposed") is True,
        "expected_alias": expected_alias,
        "profile_config_model_repair_attempted": False,
        "profile_config_model_repaired": False,
        "profile_config_model_repaired_before_codex_exec": False,
        "profile_config_model_repaired_after_codex_exec": False,
        "profile_config_model_before": "",
        "profile_config_model_after": "",
        "profile_config_model_target": "",
        "profile_config_path_recorded": False,
        "profile_config_repair_error": "",
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
    write_json_atomic(path, dict(payload))


def _attach_live_result_text_artifact(packet: dict[str, Any], proof_dir: Path) -> dict[str, Any]:
    text = str(packet.get("live_result_text") or "")
    if packet.get("live_result_available") is not True or not text:
        return packet
    artifact_path = proof_dir / DEFAULT_LIVE_RESULT_TEXT_ARTIFACT_FILENAME
    write_text_atomic(artifact_path, text)
    artifact_bytes = artifact_path.stat().st_size
    changed_files = [
        str(item)
        for item in (
            packet.get("changed_files")
            if isinstance(packet.get("changed_files"), list)
            else []
        )
    ]
    if str(artifact_path) not in changed_files:
        changed_files.append(str(artifact_path))
    packet.update(
        {
            "changed_files": changed_files,
            "live_result_text_artifact_written": True,
            "live_result_text_artifact_filename": DEFAULT_LIVE_RESULT_TEXT_ARTIFACT_FILENAME,
            "live_result_text_artifact_path_recorded": False,
            "live_result_text_artifact_sha256": _sha256_text(text),
            "live_result_text_artifact_bytes": artifact_bytes,
        }
    )
    return packet


def _json_string_content(value: str, *, ensure_ascii: bool) -> str:
    return json.dumps(value, ensure_ascii=ensure_ascii)[1:-1]


def _redaction_replacements(*, task: str, prompt: str) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for label, value in (
        ("task", task),
        ("codex-prompt", prompt),
    ):
        if not value:
            continue
        replacement = f"<redacted-{label}-sha256:{_sha256_text(value)}>"
        for candidate in (
            value,
            _json_string_content(value, ensure_ascii=True),
            _json_string_content(value, ensure_ascii=False),
        ):
            if candidate:
                replacements[candidate] = replacement
    return replacements


def _redact_text_file(path: Path, replacements: Mapping[str, str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    redacted = text
    for raw, replacement in sorted(
        replacements.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        redacted = redacted.replace(raw, replacement)
    if redacted == text:
        return False
    path.write_text(redacted, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wbp_dip")
    parser.add_argument("task", nargs="*")
    parser.add_argument("--alias", default=DEFAULT_ALIAS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sandbox", default=DEFAULT_SANDBOX)
    parser.add_argument("--profile-dir")
    parser.add_argument("--codex-bin")
    parser.add_argument("--cd", dest="repo_root", default=str(Path.cwd()))
    parser.add_argument(
        "--repo-bridge",
        choices=REPO_BRIDGE_MODES,
        default=DEFAULT_REPO_BRIDGE_MODE,
        help="allow WBP-mediated controlled repo/action tools for development tasks",
    )
    parser.add_argument(
        "--work-mode",
        choices=DIP_WORK_MODES,
        default=DEFAULT_DIP_WORK_MODE,
        help="use standard bounded proof output or fuller DIP work output",
    )
    parser.add_argument("--proof-dir")
    parser.add_argument("--output-jsonl")
    parser.add_argument("--output-last-message")
    parser.add_argument("--entry-evidence-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--proof-only",
        action="store_true",
        help="prove Custom Codex MCP dispatch without requiring a live user-facing result",
    )
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
    python_bin = default_python_bin()
    model = _safe_text(args.model, limit=80) or DEFAULT_MODEL
    sandbox = _safe_text(args.sandbox, limit=80) or DEFAULT_SANDBOX
    prompt = build_delegate_prompt(task=task, expected_alias=expected_alias)
    argv_to_run = build_codex_exec_argv(
        codex_bin=codex_bin,
        python_bin=python_bin,
        repo_root=repo_root,
        model=model,
        sandbox=sandbox,
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
            require_live_result=False,
            dip_work_mode=args.work_mode,
        )
        dry_packet.update(
            {
                "planned_codex_exec": True,
                "planned_sandbox": sandbox,
                "planned_model": model,
                "planned_dip_work_mode": args.work_mode,
                "planned_prompt_sha256": _sha256_text(prompt),
                "profile_config_model_repair_planned": True,
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
    profile_repair_before = _repair_stale_profile_config_model(profile_dir, model=model)
    profile_repair_after: dict[str, Any] = {
        **profile_repair_before,
        "profile_config_model_repaired": False,
        "profile_config_model_repair_attempted": False,
    }
    if codex_executable and task:
        with output_jsonl.open("w", encoding="utf-8") as stdout_handle:
            completed = subprocess.run(
                argv_to_run,
                cwd=str(repo_root),
                env=env,
                stdout=stdout_handle,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
        codex_exit_code = int(completed.returncode)
        redactions = _redaction_replacements(task=task, prompt=prompt)
        _redact_text_file(output_jsonl, redactions)
        _redact_text_file(output_last_message, redactions)
        profile_repair_after = _repair_stale_profile_config_model(profile_dir, model=model)
    live_result: dict[str, Any] | None = None
    if not args.proof_only and codex_exit_code == 0:
        delegate_packet = _find_delegate_packet(_read_codex_exec_jsonl(output_jsonl))
        if _delegate_packet_ok(delegate_packet):
            live_result = request_live_result(
                task=task,
                expected_alias=expected_alias,
                profile_dir=profile_dir,
                repo_root=repo_root,
                repo_bridge_mode=args.repo_bridge,
                dip_work_mode=args.work_mode,
            )
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
        live_result=live_result,
        require_live_result=not args.proof_only,
        dip_work_mode=args.work_mode,
    )
    packet.update(
        _merge_profile_config_repair_packets(profile_repair_before, profile_repair_after)
    )
    packet = _attach_live_result_text_artifact(packet, proof_dir)
    packet_file = proof_dir / "wbp-dip-tool.packet.json"
    _write_json(packet_file, packet)
    if args.json:
        sys.stdout.write(json.dumps(packet, ensure_ascii=True, sort_keys=True) + "\n")
    else:
        if packet.get("live_result_available") is True and str(packet.get("live_result_text", "")).strip():
            result_text = str(packet["live_result_text"])
            sys.stdout.write(result_text)
            if not result_text.endswith("\n"):
                sys.stdout.write("\n")
        elif output_last_message.is_file():
            last_message = output_last_message.read_text(encoding="utf-8")
            sys.stdout.write(last_message)
            if not last_message.endswith("\n"):
                sys.stdout.write("\n")
        else:
            sys.stdout.write(str(packet["human_message"]) + "\n")
    return int(packet["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
