# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Proof runner for the official Codex MCP admission path."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Mapping, Sequence

from . import mcp_delegate
from .cli_runner_via_wbp import PRIMARY_MODEL_ID
from .core import packets
from .process_runner import BoundedProcessResult, PROCESS_OK, run_bounded_process


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CODEX_MODEL_ID = PRIMARY_MODEL_ID
DEFAULT_ROUTE_ID = "wbp-deepseek-chat"
DEFAULT_STALE_ROUTE_ID = "wbp-deepseek-v3"
DEFAULT_TIMEOUT_SECONDS = 180
OFFICIAL_MCP_ADMISSION_CASE_PACKET_KIND = "wbp_official_mcp_admission_case"
OFFICIAL_MCP_ADMISSION_MATRIX_PACKET_KIND = "wbp_official_mcp_admission_matrix"
NATURAL_ALIAS_INTENT_MATRIX_PACKET_KIND = "wbp_natural_alias_intent_matrix"
NATURAL_INTENT_CLAIM_PACKET_KIND = "wbp_natural_intent_claim"
OFFICIAL_MCP_ADMISSION_NOT_PROVEN = "WBP_OFFICIAL_MCP_ADMISSION_NOT_PROVEN"
OFFICIAL_MCP_TOOL_CALL_NOT_BOUND = "WBP_OFFICIAL_MCP_TOOL_CALL_NOT_BOUND"
NATURAL_MCP_TOOL_CALL_NOT_BOUND = "WBP_NATURAL_MCP_TOOL_CALL_NOT_BOUND"
OFFICIAL_MCP_ALIAS_MISMATCH = "WBP_OFFICIAL_MCP_ALIAS_MISMATCH"
NATURAL_INTENT_CLAIM_NOT_PROVEN = "WBP_NATURAL_INTENT_CLAIM_NOT_PROVEN"
NATURAL_INTENT_ALIAS_MISSING = "WBP_NATURAL_INTENT_ALIAS_MISSING"
NATURAL_INTENT_ALIAS_OUTSIDE_CONTEXT = "WBP_NATURAL_INTENT_ALIAS_OUTSIDE_CONTEXT"
NATURAL_INTENT_TASK_MISSING = "WBP_NATURAL_INTENT_TASK_MISSING"
NATURAL_INTENT_AMBIGUOUS = "WBP_NATURAL_INTENT_AMBIGUOUS"
INTENT_TOOL_DIRECTED = "tool_directed"
INTENT_STRICT_NATURAL = "strict_natural"
INTENT_AMBIGUOUS_NATURAL = "ambiguous_natural"
INTENT_NO_ALIAS_NEGATIVE = "no_alias_negative"
NATURAL_SHAPE_EXACT_STABLE_TASK = "exact_stable_task"
NATURAL_SHAPE_QUOTED_PAYLOAD = "quoted_payload"
NATURAL_SHAPE_COLON_DELIMITED_TASK = "colon_delimited_task"
NATURAL_SHAPE_LOOSE_SEMANTIC_TASK = "loose_semantic_task"
NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK = "ambiguous_unsafe_task"
NATURAL_BINDING_SUPPORTED = "binding_supported"
NATURAL_BINDING_BLOCKED = "binding_blocked"
NATURAL_REQUIRES_EXACT_TASK_SHAPE = "requires_exact_task_shape"
NATURAL_REQUIRES_HOOK_INTERCEPTOR = "requires_hook_interceptor"
NATURAL_AMBIGUOUS_FAIL_CLOSED = "ambiguous_fail_closed"
CANON_RULE_EXACT_STABLE_TASK = "exact_stable_task_v1"
CANON_RULE_QUOTED_PAYLOAD_UNWRAP = "quoted_payload_unwrap_v1"
CANON_RULE_COLON_DELIMITED_EXACT = "colon_delimited_exact_v1"
CANON_RULE_UNSUPPORTED = "unsupported_v1"


@dataclass(frozen=True)
class OfficialMcpAdmissionVariant:
    name: str
    prompt: str
    expected_alias: str
    coding_aliases: tuple[str, ...]
    expect_positive_proof: bool
    expected_task: str = ""
    intent_kind: str = INTENT_TOOL_DIRECTED
    required_for_natural_matrix: bool = True
    bind_expected_delegate_arguments: bool = True
    per_tool_approval: bool = True
    approval_policy: str = ""
    write_context: bool = True
    route_id: str = DEFAULT_ROUTE_ID
    allowed_api_route_ids: tuple[str, ...] = (DEFAULT_ROUTE_ID,)
    forbidden_stale_route_ids: tuple[str, ...] = (DEFAULT_STALE_ROUTE_ID,)


def default_admission_variants() -> list[OfficialMcpAdmissionVariant]:
    return [
        OfficialMcpAdmissionVariant(
            name="positive_dip_per_tool_approve",
            prompt=(
                "Call the WBP MCP tool delegate_to_dip exactly once with "
                'task="WBP_OFFICIAL_MCP_DIP_CORE_PROOF" and expected_alias="DIP". '
                "Do not answer locally and do not create a sub-agent."
            ),
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            expected_task="WBP_OFFICIAL_MCP_DIP_CORE_PROOF",
        ),
        OfficialMcpAdmissionVariant(
            name="positive_agent_2_per_tool_approve",
            prompt=(
                "Call the WBP MCP tool delegate_to_dip exactly once with "
                'task="WBP_OFFICIAL_MCP_AGENT_2_CORE_PROOF" and '
                'expected_alias="Agent 2". Do not answer locally.'
            ),
            expected_alias="Agent 2",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            expected_task="WBP_OFFICIAL_MCP_AGENT_2_CORE_PROOF",
        ),
        OfficialMcpAdmissionVariant(
            name="positive_custom_alias_per_tool_approve",
            prompt=(
                "Call the WBP MCP tool delegate_to_dip exactly once with "
                'task="WBP_OFFICIAL_MCP_WORKER_CORE_PROOF" and '
                'expected_alias="Worker". Do not answer locally.'
            ),
            expected_alias="Worker",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            expected_task="WBP_OFFICIAL_MCP_WORKER_CORE_PROOF",
        ),
        OfficialMcpAdmissionVariant(
            name="negative_no_approval_policy_never",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            per_tool_approval=False,
            approval_policy="never",
        ),
        OfficialMcpAdmissionVariant(
            name="negative_missing_alias_context",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            write_context=False,
        ),
        OfficialMcpAdmissionVariant(
            name="negative_route_outside_allowlist",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            route_id=DEFAULT_ROUTE_ID,
            allowed_api_route_ids=("wbp-other-route",),
        ),
    ]


def default_natural_alias_intent_variants() -> list[OfficialMcpAdmissionVariant]:
    return [
        OfficialMcpAdmissionVariant(
            name="strict_natural_dip",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="strict_natural_agent_2",
            prompt="Agent 2, проверь контракт допуска WBP.",
            expected_alias="Agent 2",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="strict_natural_worker",
            prompt="Worker, сделай короткий план проверки.",
            expected_alias="Worker",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="ambiguous_second_agent_ru",
            prompt="Пусть второй агент посмотрит это.",
            expected_alias="Agent 2",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_AMBIGUOUS_NATURAL,
            required_for_natural_matrix=False,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="ambiguous_coder_ru",
            prompt="Передай кодеру короткую задачу.",
            expected_alias="Worker",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_AMBIGUOUS_NATURAL,
            required_for_natural_matrix=False,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="ambiguous_coding_agent_en",
            prompt="Ask the coding agent to review this briefly.",
            expected_alias="Worker",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=INTENT_AMBIGUOUS_NATURAL,
            required_for_natural_matrix=False,
            bind_expected_delegate_arguments=False,
        ),
        OfficialMcpAdmissionVariant(
            name="negative_no_approval_strict_natural",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
            per_tool_approval=False,
            approval_policy="never",
        ),
        OfficialMcpAdmissionVariant(
            name="negative_missing_alias_context_strict_natural",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
            write_context=False,
        ),
        OfficialMcpAdmissionVariant(
            name="negative_route_outside_allowlist_strict_natural",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            intent_kind=INTENT_STRICT_NATURAL,
            bind_expected_delegate_arguments=False,
            route_id=DEFAULT_ROUTE_ID,
            allowed_api_route_ids=("wbp-other-route",),
        ),
        OfficialMcpAdmissionVariant(
            name="negative_no_alias_prompt",
            prompt="Сделай короткий план проверки.",
            expected_alias="",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            intent_kind=INTENT_NO_ALIAS_NEGATIVE,
            bind_expected_delegate_arguments=False,
        ),
    ]


def runtime_context_payload(variant: OfficialMcpAdmissionVariant) -> dict[str, Any]:
    aliases = list(variant.coding_aliases)
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "execution_mode": "chatgpt_plus_api",
        "agent_bindings_status": "ok",
        "primary_aliases": ["Codex", "Agent 1"],
        "coding_aliases": aliases,
        "allowed_api_route_ids": list(variant.allowed_api_route_ids),
        "forbidden_stale_route_ids": list(variant.forbidden_stale_route_ids),
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": "chatgpt_account",
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": aliases,
                "lane": "api_route",
                "enabled": True,
                "route_id": variant.route_id,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def write_runtime_context(
    profile_dir: Path,
    variant: OfficialMcpAdmissionVariant,
) -> Path:
    profile_dir.mkdir(parents=True, exist_ok=True)
    context_path = profile_dir / "wbp-agent-runtime-context.json"
    context_path.write_text(
        json.dumps(runtime_context_payload(variant), ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return context_path


def _toml_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=True)


def _toml_array(values: Sequence[str]) -> str:
    return "[" + ",".join(_toml_string(value) for value in values) + "]"


def _toml_inline_env(values: Mapping[str, str | Path]) -> str:
    return "{" + ",".join(
        f"{key}={_toml_string(value)}" for key, value in sorted(values.items())
    ) + "}"


def codex_mcp_config_overrides(
    *,
    profile_dir: Path,
    evidence_path: Path,
    per_tool_approval: bool,
    approval_policy: str = "",
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    overrides = [
        'mcp_servers.wbp.command="python3"',
        f"mcp_servers.wbp.args={_toml_array(['-m', 'wild_boar_proxy.mcp_delegate'])}",
        f"mcp_servers.wbp.enabled_tools={_toml_array([mcp_delegate.DELEGATE_TO_DIP_TOOL])}",
        "mcp_servers.wbp.supports_parallel_tool_calls=false",
        (
            "mcp_servers.wbp.env="
            + _toml_inline_env(
                {
                    "PYTHONPATH": repo_root,
                    "WBP_ENTRY_HOOK_EVIDENCE_PATH": evidence_path,
                    "WBP_PROFILE_DIR": profile_dir,
                }
            )
        ),
    ]
    if per_tool_approval:
        overrides.append(
            f'mcp_servers.wbp.tools.{mcp_delegate.DELEGATE_TO_DIP_TOOL}.approval_mode="approve"'
        )
    if approval_policy:
        overrides.append(f"approval_policy={_toml_string(approval_policy)}")
    return overrides


def _codex_config_args(overrides: Sequence[str]) -> list[str]:
    args: list[str] = []
    for override in overrides:
        args.extend(["-c", override])
    return args


def _proof_env(*, codex_home: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": os.environ.get("HOME", ""),
    }
    env["CODEX_HOME"] = str(codex_home)
    env.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    env.setdefault("no_proxy", "127.0.0.1,localhost,::1")
    return env


def _expected_delegate_arguments(variant: OfficialMcpAdmissionVariant) -> dict[str, str]:
    if not variant.bind_expected_delegate_arguments:
        return {}
    return {
        "task": variant.expected_task or variant.prompt,
        "expected_alias": variant.expected_alias,
    }


def _strict_natural_delegated_task(prompt: str, alias: str) -> str:
    safe_prompt = mcp_delegate._safe_text(prompt, limit=4096)
    safe_alias = mcp_delegate._safe_text(alias, limit=80)
    if not safe_prompt or not safe_alias:
        return ""
    alias_index = safe_prompt.casefold().find(safe_alias.casefold())
    if alias_index < 0:
        return ""
    tail = safe_prompt[alias_index + len(safe_alias) :]
    if ":" in tail:
        tail = tail.split(":", 1)[1]
    return mcp_delegate._safe_text(tail.lstrip(" \t,;:-—–"), limit=4096)


def _strip_wrapping_quotes(value: str) -> tuple[str, bool]:
    text = mcp_delegate._safe_text(value, limit=4096)
    quote_pairs = (('"', '"'), ("'", "'"), ("«", "»"), ("“", "”"), ("`", "`"))
    for left, right in quote_pairs:
        if text.startswith(left) and text.endswith(right) and len(text) >= 2:
            return mcp_delegate._safe_text(text[1:-1], limit=4096), True
    return text, False


def _natural_command_shape(
    *,
    variant: OfficialMcpAdmissionVariant,
    delegated_task: str,
    alias_present: bool,
) -> str:
    if variant.intent_kind == INTENT_AMBIGUOUS_NATURAL:
        return NATURAL_SHAPE_LOOSE_SEMANTIC_TASK
    if variant.intent_kind == INTENT_NO_ALIAS_NEGATIVE or not alias_present:
        return NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK
    if variant.intent_kind != INTENT_STRICT_NATURAL or not delegated_task:
        return NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK
    unquoted, had_wrapping_quotes = _strip_wrapping_quotes(delegated_task)
    if had_wrapping_quotes and unquoted:
        return NATURAL_SHAPE_QUOTED_PAYLOAD
    task_key = unquoted.casefold()
    if task_key.startswith("ответь ровно строкой:"):
        return NATURAL_SHAPE_EXACT_STABLE_TASK
    return NATURAL_SHAPE_COLON_DELIMITED_TASK


def _binding_status_for_shape(shape: str) -> str:
    if shape in {
        NATURAL_SHAPE_EXACT_STABLE_TASK,
        NATURAL_SHAPE_QUOTED_PAYLOAD,
        NATURAL_SHAPE_COLON_DELIMITED_TASK,
    }:
        return NATURAL_BINDING_SUPPORTED
    if shape == NATURAL_SHAPE_LOOSE_SEMANTIC_TASK:
        return NATURAL_REQUIRES_HOOK_INTERCEPTOR
    if shape == NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK:
        return NATURAL_AMBIGUOUS_FAIL_CLOSED
    return NATURAL_BINDING_BLOCKED


def _canonicalize_delegated_task(
    *,
    shape: str,
    delegated_task: str,
) -> tuple[str, str, bool]:
    safe_task = mcp_delegate._safe_text(delegated_task, limit=4096)
    if not safe_task:
        return "", CANON_RULE_UNSUPPORTED, False
    if shape == NATURAL_SHAPE_QUOTED_PAYLOAD:
        unquoted, had_wrapping_quotes = _strip_wrapping_quotes(safe_task)
        if had_wrapping_quotes and unquoted:
            return unquoted, CANON_RULE_QUOTED_PAYLOAD_UNWRAP, True
        return "", CANON_RULE_UNSUPPORTED, False
    if shape == NATURAL_SHAPE_EXACT_STABLE_TASK:
        return safe_task, CANON_RULE_EXACT_STABLE_TASK, True
    if shape == NATURAL_SHAPE_COLON_DELIMITED_TASK:
        return safe_task, CANON_RULE_COLON_DELIMITED_EXACT, True
    return "", CANON_RULE_UNSUPPORTED, False


def _intent_claim_sha256(material: Mapping[str, Any]) -> str:
    return mcp_delegate._sha256_text(
        json.dumps(
            dict(material),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _delegated_task_candidate_sha256s(delegated_task: str) -> list[str]:
    safe_task = mcp_delegate._safe_text(delegated_task, limit=4096)
    return [mcp_delegate._sha256_text(safe_task)] if safe_task else []


def build_natural_intent_claim_packet(
    variant: OfficialMcpAdmissionVariant,
) -> dict[str, Any]:
    safe_prompt = mcp_delegate._safe_text(variant.prompt, limit=4096)
    prompt_sha256 = mcp_delegate._sha256_text(safe_prompt) if safe_prompt else ""
    strict_natural = variant.intent_kind == INTENT_STRICT_NATURAL
    ambiguous_intent = variant.intent_kind == INTENT_AMBIGUOUS_NATURAL
    alias_present = prompt_has_expected_alias(variant.prompt, variant.expected_alias)
    alias_from_runtime_context = bool(
        variant.expected_alias and variant.expected_alias in variant.coding_aliases
    )
    delegated_task = (
        _strict_natural_delegated_task(variant.prompt, variant.expected_alias)
        if strict_natural
        else ""
    )
    extracted_delegated_task_sha256 = (
        mcp_delegate._sha256_text(delegated_task) if delegated_task else ""
    )
    natural_command_shape = _natural_command_shape(
        variant=variant,
        delegated_task=delegated_task,
        alias_present=alias_present,
    )
    binding_status = _binding_status_for_shape(natural_command_shape)
    canonical_task, canonicalization_rule_id, canonicalization_supported = (
        _canonicalize_delegated_task(
            shape=natural_command_shape,
            delegated_task=delegated_task,
        )
    )
    delegated_task_sha256 = (
        mcp_delegate._sha256_text(canonical_task) if canonical_task else ""
    )
    delegated_task_candidate_sha256s = _delegated_task_candidate_sha256s(
        canonical_task
    )
    ok = bool(
        strict_natural
        and not ambiguous_intent
        and alias_present
        and alias_from_runtime_context
        and binding_status == NATURAL_BINDING_SUPPORTED
        and canonicalization_supported
        and delegated_task_sha256
    )
    blocking_reasons: list[str] = []
    if ambiguous_intent:
        blocking_reasons.append("ambiguous_intent")
    if not strict_natural:
        blocking_reasons.append("not_strict_natural_intent")
    if not alias_present:
        blocking_reasons.append("alias_not_present_in_prompt")
    if not alias_from_runtime_context:
        blocking_reasons.append("alias_not_from_runtime_context")
    if binding_status != NATURAL_BINDING_SUPPORTED:
        blocking_reasons.append(binding_status)
    if not canonicalization_supported:
        blocking_reasons.append("canonicalization_not_supported")
    if not delegated_task_sha256:
        blocking_reasons.append("delegated_task_digest_missing")

    if ok:
        machine_error_code = "OK"
    elif ambiguous_intent:
        machine_error_code = NATURAL_INTENT_AMBIGUOUS
    elif not alias_present:
        machine_error_code = NATURAL_INTENT_ALIAS_MISSING
    elif not alias_from_runtime_context:
        machine_error_code = NATURAL_INTENT_ALIAS_OUTSIDE_CONTEXT
    elif not delegated_task_sha256:
        machine_error_code = NATURAL_INTENT_TASK_MISSING
    else:
        machine_error_code = NATURAL_INTENT_CLAIM_NOT_PROVEN

    claim_material = {
        "packet_kind": NATURAL_INTENT_CLAIM_PACKET_KIND,
        "prompt_sha256": prompt_sha256,
        "alias": variant.expected_alias if alias_present else "",
        "alias_from_runtime_context": alias_from_runtime_context,
        "natural_command_shape": natural_command_shape,
        "binding_status": binding_status,
        "canonicalization_rule_id": canonicalization_rule_id,
        "canonicalization_supported": canonicalization_supported,
        "canonicalization_input_sha256": extracted_delegated_task_sha256,
        "canonicalization_output_sha256": delegated_task_sha256,
        "delegated_task_sha256": delegated_task_sha256,
        "delegated_task_candidate_sha256s": delegated_task_candidate_sha256s,
        "delegated_task_candidate_digest_count": len(
            delegated_task_candidate_sha256s
        ),
        "delegated_task_source": "natural_prompt_parser" if delegated_task_sha256 else "",
        "ambiguous_intent": ambiguous_intent,
    }
    intent_claim_sha256 = _intent_claim_sha256(claim_material) if ok else ""
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Natural prompt intent claim was produced."
            if ok
            else "Natural prompt intent claim was not produced."
        ),
        machine_error_code=machine_error_code,
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        extra={
            "schema_version": 1,
            "packet_kind": NATURAL_INTENT_CLAIM_PACKET_KIND,
            "prompt_digest_present": bool(prompt_sha256),
            "prompt_sha256": prompt_sha256 if ok else "",
            "intent_claim_digest_present": bool(intent_claim_sha256),
            "intent_claim_sha256": intent_claim_sha256,
            "alias": variant.expected_alias if alias_present else "",
            "alias_from_runtime_context": alias_from_runtime_context,
            "natural_command_shape": natural_command_shape,
            "binding_status": binding_status,
            "canonicalization_rule_id": canonicalization_rule_id,
            "canonicalization_supported": canonicalization_supported,
            "canonicalization_input_digest_present": bool(
                extracted_delegated_task_sha256
            ),
            "canonicalization_input_sha256": extracted_delegated_task_sha256,
            "canonicalization_output_digest_present": bool(delegated_task_sha256),
            "canonicalization_output_sha256": delegated_task_sha256,
            "delegated_task_digest_present": bool(delegated_task_sha256),
            "delegated_task_sha256": delegated_task_sha256,
            "delegated_task_candidate_sha256s": delegated_task_candidate_sha256s,
            "delegated_task_candidate_digest_count": len(
                delegated_task_candidate_sha256s
            ),
            "delegated_task_source": (
                "natural_prompt_parser" if delegated_task_sha256 else ""
            ),
            "ambiguous_intent": ambiguous_intent,
            "raw_prompt_recorded": False,
            "raw_task_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "product_ready": False,
            "custom_codex_ui_visibility_proven": False,
            "blocking_reasons": [] if ok else blocking_reasons,
        },
    )


def _intent_claim_for_variant(
    variant: OfficialMcpAdmissionVariant,
) -> dict[str, Any]:
    if variant.intent_kind not in {
        INTENT_STRICT_NATURAL,
        INTENT_AMBIGUOUS_NATURAL,
        INTENT_NO_ALIAS_NEGATIVE,
    }:
        return {}
    return build_natural_intent_claim_packet(variant)


def explicit_tool_instruction_used(prompt: str) -> bool:
    lowered = prompt.casefold()
    explicit_markers = (
        "delegate_to_dip",
        "mcp",
        "tool",
        "expected_alias",
        "json",
        "call the wbp",
        "invoke",
        "вызови tool",
    )
    return any(marker in lowered for marker in explicit_markers)


def prompt_has_expected_alias(prompt: str, expected_alias: str) -> bool:
    if not expected_alias:
        return False
    prompt_key = " ".join(str(prompt or "").split()).casefold()
    alias_key = " ".join(str(expected_alias or "").split()).casefold()
    return bool(alias_key and alias_key in prompt_key)


def _first_non_ok_machine_error_code(*values: object) -> str:
    for value in values:
        code = str(value or "").strip()
        if code and code != "OK":
            return code
    return ""


def _load_entry_evidence(evidence_path: Path) -> dict[str, Any]:
    if not evidence_path.exists():
        return {}
    try:
        parsed = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_official_mcp_admission_case_packet(
    *,
    variant: OfficialMcpAdmissionVariant,
    config_packet: Mapping[str, Any],
    prompt_packet: Mapping[str, Any],
    codex_tool_call_packet: Mapping[str, Any],
    entry_hook_evidence: Mapping[str, Any],
    codex_exec_exit_code: int | None,
    codex_exec_machine_error_code: str,
    codex_mcp_get_exit_code: int | None,
    uses_danger_full_access: bool,
    uses_dangerously_bypass: bool,
    raw_jsonl_recorded: bool = False,
    raw_prompt_recorded: bool = False,
) -> dict[str, Any]:
    evidence = dict(entry_hook_evidence)
    config_loaded = bool(config_packet.get("codex_mcp_config_loaded") is True)
    tool_call_observed = bool(
        codex_tool_call_packet.get("delegate_to_dip_tool_called") is True
    )
    tool_call_completed = bool(
        codex_tool_call_packet.get("delegate_to_dip_tool_call_completed") is True
    )
    prompt_bound = bool(
        codex_tool_call_packet.get("prompt_to_mcp_call_bound") is True
    )
    entry_ok = bool(evidence.get("status") == "ok")
    alias_context_read = evidence.get("alias_context_read") is True
    api_lane_called = evidence.get("api_lane_called") is True
    route_bound_dispatch_proven = evidence.get("route_bound_dispatch_proven") is True
    local_imitation_used = bool(
        evidence.get("local_imitation_used") is True
        or codex_tool_call_packet.get("local_imitation_used") is True
    )
    fallback_used = bool(evidence.get("fallback_used") is True)
    secrets_exposed = bool(
        evidence.get("secret_value_exposed") is True
        or evidence.get("raw_backend_details_exposed") is True
        or codex_tool_call_packet.get("secret_value_exposed") is True
    )
    native_codex_subagent_used_as_dip = bool(
        codex_tool_call_packet.get("codex_subagent_used_as_dip") is True
        or codex_tool_call_packet.get("local_codex_subagent_used_as_dip") is True
    )
    selected_alias_matches_expected = bool(
        str(evidence.get("selected_alias") or "") == variant.expected_alias
    )
    natural_prompt_used = variant.intent_kind in {
        INTENT_STRICT_NATURAL,
        INTENT_AMBIGUOUS_NATURAL,
        INTENT_NO_ALIAS_NEGATIVE,
    }
    strict_natural_prompt = variant.intent_kind == INTENT_STRICT_NATURAL
    ambiguous_natural_prompt = variant.intent_kind == INTENT_AMBIGUOUS_NATURAL
    no_alias_negative_prompt = variant.intent_kind == INTENT_NO_ALIAS_NEGATIVE
    explicit_tool_instruction = explicit_tool_instruction_used(variant.prompt)
    expected_alias_present_in_prompt = prompt_has_expected_alias(
        variant.prompt,
        variant.expected_alias,
    )
    intent_claim_digest_bound = (
        codex_tool_call_packet.get("intent_claim_digest_bound") is True
    )
    tool_call_task_matches_intent = (
        codex_tool_call_packet.get("tool_call_task_matches_intent") is True
    )
    natural_binding_required = strict_natural_prompt
    tool_call_completed_but_prompt_not_bound = bool(
        tool_call_completed and not prompt_bound
    )
    natural_mcp_tool_call_unbound = bool(
        natural_prompt_used
        and tool_call_completed_but_prompt_not_bound
    )
    positive_proof = bool(
        config_loaded
        and tool_call_observed
        and tool_call_completed
        and prompt_bound
        and entry_ok
        and alias_context_read
        and selected_alias_matches_expected
        and evidence.get("selected_alias_lane") == "api_route"
        and evidence.get("allowed_api_route_ids_enforced") is True
        and api_lane_called
        and route_bound_dispatch_proven
        and not local_imitation_used
        and not fallback_used
        and not native_codex_subagent_used_as_dip
        and not secrets_exposed
        and not uses_danger_full_access
        and not uses_dangerously_bypass
        and not raw_jsonl_recorded
        and not raw_prompt_recorded
        and (not natural_binding_required or intent_claim_digest_bound)
    )
    natural_alias_intent_routed = bool(
        natural_prompt_used
        and positive_proof
        and not explicit_tool_instruction
        and (
            expected_alias_present_in_prompt
            or ambiguous_natural_prompt
            or no_alias_negative_prompt
        )
    )
    fail_closed = bool(
        not positive_proof
        and not local_imitation_used
        and not fallback_used
        and not secrets_exposed
        and not uses_danger_full_access
        and not uses_dangerously_bypass
    )
    expectation_met = (
        positive_proof if variant.expect_positive_proof else fail_closed
    )
    blocking_reasons: list[str] = []
    if not config_loaded:
        blocking_reasons.append("codex_mcp_config_not_loaded")
    if not tool_call_observed:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    elif not tool_call_completed:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_completed")
    if tool_call_completed and not prompt_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")
    if natural_binding_required and not intent_claim_digest_bound:
        blocking_reasons.append("intent_claim_digest_not_bound")
    if not entry_ok:
        blocking_reasons.append(
            str(evidence.get("machine_error_code") or "entry_hook_evidence_not_ok")
        )
    if not alias_context_read:
        blocking_reasons.append("alias_context_not_read")
    if entry_ok and not selected_alias_matches_expected:
        blocking_reasons.append("selected_alias_did_not_match_expected_alias")
    if evidence and evidence.get("allowed_api_route_ids_enforced") is not True:
        blocking_reasons.append("allowed_api_route_ids_not_enforced")
    if not api_lane_called:
        blocking_reasons.append("api_lane_not_called")
    if not route_bound_dispatch_proven:
        blocking_reasons.append("route_bound_dispatch_not_proven")
    if native_codex_subagent_used_as_dip:
        blocking_reasons.append("native_codex_subagent_used_as_dip")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if secrets_exposed:
        blocking_reasons.append("secret_or_backend_detail_exposed")
    if uses_danger_full_access:
        blocking_reasons.append("danger_full_access_used")
    if uses_dangerously_bypass:
        blocking_reasons.append("dangerously_bypass_used")
    if raw_jsonl_recorded:
        blocking_reasons.append("raw_jsonl_recorded")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_recorded")

    if positive_proof:
        proof_machine_error_code = "OK"
    elif entry_ok and not selected_alias_matches_expected:
        proof_machine_error_code = OFFICIAL_MCP_ALIAS_MISMATCH
    elif tool_call_completed_but_prompt_not_bound:
        proof_machine_error_code = (
            NATURAL_MCP_TOOL_CALL_NOT_BOUND
            if natural_mcp_tool_call_unbound
            else OFFICIAL_MCP_TOOL_CALL_NOT_BOUND
        )
    elif natural_binding_required and not intent_claim_digest_bound:
        proof_machine_error_code = NATURAL_MCP_TOOL_CALL_NOT_BOUND
    else:
        proof_machine_error_code = _first_non_ok_machine_error_code(
            evidence.get("machine_error_code"),
            codex_tool_call_packet.get("machine_error_code"),
            config_packet.get("machine_error_code"),
        ) or OFFICIAL_MCP_ADMISSION_NOT_PROVEN
    return packets.build_command_packet(
        ok=expectation_met,
        human_message=(
            "Official Codex MCP admission proof expectation was met."
            if expectation_met
            else "Official Codex MCP admission proof expectation was not met."
        ),
        machine_error_code="OK" if expectation_met else proof_machine_error_code,
        liveness="healthy" if expectation_met else "degraded",
        severity="recoverable",
        operator_action="none" if expectation_met else "stop",
        changed_files=[],
        extra={
            "schema_version": 1,
            "packet_kind": OFFICIAL_MCP_ADMISSION_CASE_PACKET_KIND,
            "variant": variant.name,
            "expected_alias": variant.expected_alias,
            "intent_kind": variant.intent_kind,
            "required_for_natural_matrix": variant.required_for_natural_matrix,
            "expect_positive_proof": variant.expect_positive_proof,
            "expectation_met": expectation_met,
            "positive_proof": positive_proof,
            "natural_prompt_used": natural_prompt_used,
            "strict_natural_prompt": strict_natural_prompt,
            "ambiguous_natural_prompt": ambiguous_natural_prompt,
            "no_alias_negative_prompt": no_alias_negative_prompt,
            "explicit_tool_instruction_used": explicit_tool_instruction,
            "expected_alias_present_in_prompt": expected_alias_present_in_prompt,
            "natural_alias_intent_routed": natural_alias_intent_routed,
            "natural_alias_intent_result": (
                "routed"
                if natural_alias_intent_routed
                else "not_routed"
                if natural_prompt_used
                else "not_applicable"
            ),
            "fail_closed": fail_closed,
            "proof_machine_error_code": proof_machine_error_code,
            "proof_blocking_reasons": [] if positive_proof else blocking_reasons,
            "codex_mcp_config_loaded": config_loaded,
            "codex_mcp_get_exit_code": codex_mcp_get_exit_code,
            "codex_exec_exit_code": codex_exec_exit_code,
            "codex_exec_machine_error_code": codex_exec_machine_error_code,
            "codex_mcp_tool_called": tool_call_observed,
            "delegate_to_dip_called": tool_call_observed,
            "delegate_to_dip_tool_call_completed": tool_call_completed,
            "prompt_to_mcp_call_bound": prompt_bound,
            "tool_call_completed_but_prompt_not_bound": (
                tool_call_completed_but_prompt_not_bound
            ),
            "natural_mcp_tool_call_unbound": natural_mcp_tool_call_unbound,
            "tool_call_digest_present": (
                codex_tool_call_packet.get("tool_call_digest_present") is True
            ),
            "tool_call_task_digest_present": (
                codex_tool_call_packet.get("tool_call_task_digest_present") is True
            ),
            "tool_call_task_sha256": str(
                codex_tool_call_packet.get("tool_call_task_sha256") or ""
            ),
            "expected_delegate_tool_call_digest_present": (
                codex_tool_call_packet.get(
                    "expected_delegate_tool_call_digest_present"
                )
                is True
            ),
            "expected_delegate_tool_call_matched": (
                codex_tool_call_packet.get("expected_delegate_tool_call_matched")
                is True
            ),
            "prompt_digest_present": (
                codex_tool_call_packet.get("prompt_digest_present") is True
            ),
            "prompt_task_digest_matched": (
                codex_tool_call_packet.get("prompt_task_digest_matched") is True
            ),
            "prompt_binding_mode": str(
                codex_tool_call_packet.get("prompt_binding_mode") or ""
            ),
            "intent_claim_digest_present": (
                codex_tool_call_packet.get("intent_claim_digest_present") is True
            ),
            "intent_claim_digest_bound": intent_claim_digest_bound,
            "natural_command_shape": str(
                codex_tool_call_packet.get("natural_command_shape") or ""
            ),
            "binding_status": str(
                codex_tool_call_packet.get("binding_status") or ""
            ),
            "canonicalization_rule_id": str(
                codex_tool_call_packet.get("canonicalization_rule_id") or ""
            ),
            "canonicalization_supported": (
                codex_tool_call_packet.get("canonicalization_supported") is True
            ),
            "canonicalization_input_digest_present": (
                codex_tool_call_packet.get("canonicalization_input_digest_present")
                is True
            ),
            "canonicalization_output_digest_present": (
                codex_tool_call_packet.get("canonicalization_output_digest_present")
                is True
            ),
            "delegated_task_digest_present": (
                codex_tool_call_packet.get("delegated_task_digest_present") is True
            ),
            "delegated_task_sha256": str(
                codex_tool_call_packet.get("delegated_task_sha256") or ""
            ),
            "delegated_task_candidate_digest_count": int(
                codex_tool_call_packet.get("delegated_task_candidate_digest_count")
                or 0
            ),
            "delegated_task_source": str(
                codex_tool_call_packet.get("delegated_task_source") or ""
            ),
            "tool_call_task_matches_intent": tool_call_task_matches_intent,
            "codex_tool_call_claim_digest_present": (
                codex_tool_call_packet.get("codex_tool_call_claim_digest_present")
                is True
            ),
            "codex_tool_call_claim_sha256": str(
                codex_tool_call_packet.get("codex_tool_call_claim_sha256") or ""
            ),
            "alias_context_read": alias_context_read,
            "selected_alias": str(evidence.get("selected_alias") or ""),
            "selected_alias_matches_expected": selected_alias_matches_expected,
            "selected_alias_lane": str(evidence.get("selected_alias_lane") or ""),
            "allowed_api_route_ids_enforced": (
                evidence.get("allowed_api_route_ids_enforced") is True
            ),
            "api_lane_called": api_lane_called,
            "route_bound_dispatch_proven": route_bound_dispatch_proven,
            "controlled_provider_response_proven": (
                evidence.get("controlled_provider_response_proven") is True
            ),
            "local_imitation_used": local_imitation_used,
            "fallback_used": fallback_used,
            "native_codex_subagent_used_as_dip": native_codex_subagent_used_as_dip,
            "secrets_exposed": secrets_exposed,
            "uses_danger_full_access": uses_danger_full_access,
            "uses_dangerously_bypass": uses_dangerously_bypass,
            "per_tool_approval_configured": variant.per_tool_approval,
            "server_wide_approval_configured": False,
            "approval_policy": variant.approval_policy,
            "raw_jsonl_recorded": raw_jsonl_recorded,
            "raw_prompt_recorded": raw_prompt_recorded,
            "raw_task_recorded": False,
            "prompt_text_recorded": False,
            "tool_call_arguments_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": not secrets_exposed,
            "product_ready": False,
            "custom_codex_ui_visibility_proven": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "prompt_observation_packet_kind": str(prompt_packet.get("packet_kind") or ""),
            "codex_tool_call_packet_kind": str(
                codex_tool_call_packet.get("packet_kind") or ""
            ),
            "entry_hook_evidence_packet_kind": str(
                evidence.get("packet_kind") or ""
            ),
        },
    )


def build_official_mcp_admission_matrix_packet(
    case_packets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cases = [dict(packet) for packet in case_packets]
    positives = [case for case in cases if case.get("expect_positive_proof") is True]
    negatives = [case for case in cases if case.get("expect_positive_proof") is False]
    all_expectations_met = all(case.get("expectation_met") is True for case in cases)
    positive_aliases = [
        str(case.get("selected_alias") or "")
        for case in positives
        if case.get("positive_proof") is True
    ]
    required_aliases = {"DIP", "Agent 2", "Worker"}
    required_aliases_proven = required_aliases.issubset(set(positive_aliases))
    negative_fail_closed_count = sum(
        1 for case in negatives if case.get("fail_closed") is True
    )
    no_dangerous_modes = all(
        case.get("uses_danger_full_access") is False
        and case.get("uses_dangerously_bypass") is False
        for case in cases
    )
    no_raw_recording = all(
        case.get("raw_jsonl_recorded") is False
        and case.get("raw_prompt_recorded") is False
        for case in cases
    )
    ok = bool(
        cases
        and all_expectations_met
        and required_aliases_proven
        and negative_fail_closed_count >= 3
        and no_dangerous_modes
        and no_raw_recording
    )
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Official Codex MCP admission matrix proves the DIP/API-lane core path."
            if ok
            else "Official Codex MCP admission matrix does not prove the DIP/API-lane core path."
        ),
        machine_error_code="OK" if ok else "WBP_OFFICIAL_MCP_ADMISSION_MATRIX_NOT_PROVEN",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        extra={
            "schema_version": 1,
            "packet_kind": OFFICIAL_MCP_ADMISSION_MATRIX_PACKET_KIND,
            "final_status": (
                "FEATURE_CORE_PROOF_POSITIVE" if ok else "STOP_AND_DIAGNOSE"
            ),
            "case_count": len(cases),
            "positive_case_count": len(positives),
            "negative_case_count": len(negatives),
            "all_expectations_met": all_expectations_met,
            "required_positive_aliases": sorted(required_aliases),
            "positive_aliases_proven": positive_aliases,
            "required_aliases_proven": required_aliases_proven,
            "negative_fail_closed_count": negative_fail_closed_count,
            "no_dangerous_modes": no_dangerous_modes,
            "no_raw_recording": no_raw_recording,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "case_packets": cases,
        },
    )


def build_natural_alias_intent_matrix_packet(
    case_packets: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    cases = [dict(packet) for packet in case_packets]
    required_cases = [
        case for case in cases if case.get("required_for_natural_matrix") is True
    ]
    strict_required = [
        case
        for case in required_cases
        if case.get("strict_natural_prompt") is True
        and case.get("expect_positive_proof") is True
    ]
    strict_success = [
        case
        for case in strict_required
        if case.get("natural_alias_intent_routed") is True
        and case.get("selected_alias_matches_expected") is True
        and case.get("intent_claim_digest_bound") is True
        and case.get("tool_call_task_matches_intent") is True
    ]
    required_negatives = [
        case for case in required_cases if case.get("expect_positive_proof") is False
    ]
    negative_fail_closed_count = sum(
        1 for case in required_negatives if case.get("fail_closed") is True
    )
    ambiguous_cases = [
        case for case in cases if case.get("ambiguous_natural_prompt") is True
    ]
    ambiguous_routed_count = sum(
        1 for case in ambiguous_cases if case.get("natural_alias_intent_routed") is True
    )
    required_aliases = {"DIP", "Agent 2", "Worker"}
    strict_aliases_proven = [
        str(case.get("selected_alias") or "")
        for case in strict_success
        if str(case.get("selected_alias") or "")
    ]
    required_aliases_proven = required_aliases.issubset(set(strict_aliases_proven))
    alias_mismatch_count = sum(
        1
        for case in cases
        if case.get("codex_mcp_tool_called") is True
        and case.get("selected_alias_matches_expected") is False
    )
    strict_tool_call_count = sum(
        1 for case in strict_required if case.get("codex_mcp_tool_called") is True
    )
    natural_tool_call_count = sum(
        1
        for case in cases
        if case.get("natural_prompt_used") is True
        and case.get("codex_mcp_tool_called") is True
    )
    no_dangerous_modes = all(
        case.get("uses_danger_full_access") is False
        and case.get("uses_dangerously_bypass") is False
        for case in cases
    )
    no_raw_recording = all(
        case.get("raw_jsonl_recorded") is False
        and case.get("raw_prompt_recorded") is False
        and case.get("prompt_text_recorded") is False
        and case.get("raw_task_recorded") is False
        and case.get("tool_call_arguments_recorded") is False
        for case in cases
    )
    natural_command_classes = sorted(
        {
            str(case.get("natural_command_shape") or "")
            for case in cases
            if str(case.get("natural_command_shape") or "")
        }
    )
    natural_command_class_summaries: list[dict[str, Any]] = []
    for class_name in natural_command_classes:
        class_cases = [
            case
            for case in cases
            if str(case.get("natural_command_shape") or "") == class_name
        ]
        positive_count = sum(
            1 for case in class_cases if case.get("positive_proof") is True
        )
        bound_count = sum(
            1
            for case in class_cases
            if case.get("intent_claim_digest_bound") is True
            and case.get("tool_call_task_matches_intent") is True
        )
        proof_status = (
            "binding_supported"
            if positive_count == len(class_cases)
            else "binding_blocked"
            if positive_count == 0
            else "binding_partial"
        )
        natural_command_class_summaries.append(
            {
                "class_name": class_name,
                "case_count": len(class_cases),
                "positive_proof_count": positive_count,
                "intent_claim_bound_count": bound_count,
                "proof_status": proof_status,
                "binding_statuses": sorted(
                    {
                        str(case.get("binding_status") or "")
                        for case in class_cases
                        if str(case.get("binding_status") or "")
                    }
                ),
                "machine_error_codes": sorted(
                    {
                        str(case.get("machine_error_code") or "")
                        for case in class_cases
                        if str(case.get("machine_error_code") or "")
                    }
                ),
                "product_ready": False,
                "custom_codex_ui_visibility_proven": False,
            }
        )
    explicit_tool_instruction_absent_in_strict = all(
        case.get("explicit_tool_instruction_used") is False
        for case in strict_required
    )
    all_required_negatives_fail_closed = bool(
        required_negatives
        and negative_fail_closed_count == len(required_negatives)
    )
    green = bool(
        strict_required
        and len(strict_success) == len(strict_required)
        and required_aliases_proven
        and all_required_negatives_fail_closed
        and alias_mismatch_count == 0
        and no_dangerous_modes
        and no_raw_recording
        and explicit_tool_instruction_absent_in_strict
    )
    partial = bool(
        not green
        and no_dangerous_modes
        and no_raw_recording
        and (
            strict_success
            or strict_tool_call_count
            or ambiguous_routed_count
            or alias_mismatch_count
        )
    )
    if green:
        final_status = "NATURAL_ALIAS_INTENT_CORE_PROOF_POSITIVE"
        natural_alias_intent_result = "green"
    elif partial:
        final_status = "NATURAL_ALIAS_INTENT_PARTIAL"
        natural_alias_intent_result = "partial"
    else:
        final_status = "NATURAL_ALIAS_INTENT_NOT_PROVEN"
        natural_alias_intent_result = "red"
    ok = green or partial
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Natural alias intent runtime matrix routed strict natural prompts."
            if green
            else "Natural alias intent runtime matrix found only partial routing."
            if partial
            else "Natural alias intent runtime matrix did not prove natural routing."
        ),
        machine_error_code="OK" if ok else "WBP_NATURAL_ALIAS_INTENT_NOT_PROVEN",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        extra={
            "schema_version": 1,
            "packet_kind": NATURAL_ALIAS_INTENT_MATRIX_PACKET_KIND,
            "final_status": final_status,
            "natural_alias_intent_result": natural_alias_intent_result,
            "case_count": len(cases),
            "required_case_count": len(required_cases),
            "strict_required_count": len(strict_required),
            "strict_success_count": len(strict_success),
            "strict_tool_call_count": strict_tool_call_count,
            "required_positive_aliases": sorted(required_aliases),
            "strict_aliases_proven": strict_aliases_proven,
            "required_aliases_proven": required_aliases_proven,
            "required_negative_count": len(required_negatives),
            "negative_fail_closed_count": negative_fail_closed_count,
            "all_required_negatives_fail_closed": all_required_negatives_fail_closed,
            "ambiguous_case_count": len(ambiguous_cases),
            "ambiguous_routed_count": ambiguous_routed_count,
            "natural_tool_call_count": natural_tool_call_count,
            "alias_mismatch_count": alias_mismatch_count,
            "natural_command_class_count": len(natural_command_classes),
            "natural_command_class_summaries": natural_command_class_summaries,
            "explicit_tool_instruction_absent_in_strict": (
                explicit_tool_instruction_absent_in_strict
            ),
            "no_dangerous_modes": no_dangerous_modes,
            "no_raw_recording": no_raw_recording,
            "product_ready": False,
            "custom_codex_ui_visibility_proven": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "case_packets": cases,
        },
    )


def _run_codex_mcp_get(
    *,
    codex_bin: Path,
    env: Mapping[str, str],
    config_overrides: Sequence[str],
    timeout_seconds: int,
) -> BoundedProcessResult:
    return run_bounded_process(
        [str(codex_bin), "mcp", *_codex_config_args(config_overrides), "get", "wbp"],
        env=env,
        timeout_seconds=timeout_seconds,
    )


def _run_codex_exec(
    *,
    codex_bin: Path,
    env: Mapping[str, str],
    config_overrides: Sequence[str],
    model_id: str,
    prompt: str,
    workdir: Path,
    timeout_seconds: int,
) -> BoundedProcessResult:
    return run_bounded_process(
        [
            str(codex_bin),
            "exec",
            *_codex_config_args(config_overrides),
            "-m",
            model_id,
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "-C",
            str(workdir),
            "--json",
            "-",
        ],
        env=env,
        stdin_text=prompt,
        timeout_seconds=timeout_seconds,
    )


def run_official_mcp_admission_case(
    *,
    variant: OfficialMcpAdmissionVariant,
    codex_home: Path,
    proof_root: Path,
    codex_bin: Path,
    model_id: str = DEFAULT_CODEX_MODEL_ID,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    case_root = proof_root / variant.name
    profile_dir = case_root / "profile"
    workdir = case_root / "workdir"
    evidence_path = case_root / "entry-hook-evidence.json"
    case_root.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    if variant.write_context:
        write_runtime_context(profile_dir, variant)

    config_overrides = codex_mcp_config_overrides(
        profile_dir=profile_dir,
        evidence_path=evidence_path,
        per_tool_approval=variant.per_tool_approval,
        approval_policy=variant.approval_policy,
    )
    env = _proof_env(codex_home=codex_home)
    mcp_get_result = _run_codex_mcp_get(
        codex_bin=codex_bin,
        env=env,
        config_overrides=config_overrides,
        timeout_seconds=min(timeout_seconds, 60),
    )
    config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
        "",
        mcp_get_result.stdout,
        list_exit_code=0,
        get_exit_code=(
            mcp_get_result.exit_code if mcp_get_result.exit_code is not None else 1
        ),
    )
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        variant.prompt,
        source="codex_exec_json",
        expected_delegate_arguments=_expected_delegate_arguments(variant),
        intent_claim=_intent_claim_for_variant(variant),
    )
    exec_result = _run_codex_exec(
        codex_bin=codex_bin,
        env=env,
        config_overrides=config_overrides,
        model_id=model_id,
        prompt=variant.prompt,
        workdir=workdir,
        timeout_seconds=timeout_seconds,
    )
    codex_tool_call_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        exec_result.stdout,
        prompt_packet=prompt_packet,
        exec_exit_code=exec_result.exit_code or 0,
        stderr_text=exec_result.stderr,
    )
    entry_hook_evidence = _load_entry_evidence(evidence_path)
    packet = build_official_mcp_admission_case_packet(
        variant=variant,
        config_packet=config_packet,
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_tool_call_packet,
        entry_hook_evidence=entry_hook_evidence,
        codex_exec_exit_code=exec_result.exit_code,
        codex_exec_machine_error_code=exec_result.machine_error_code,
        codex_mcp_get_exit_code=mcp_get_result.exit_code,
        uses_danger_full_access=False,
        uses_dangerously_bypass=False,
    )
    (case_root / "case-packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return packet


def run_official_mcp_admission_matrix(
    *,
    codex_home: Path,
    proof_root: Path,
    codex_bin: Path | None = None,
    model_id: str = DEFAULT_CODEX_MODEL_ID,
    variants: Sequence[OfficialMcpAdmissionVariant] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    resolved_codex_bin = codex_bin or Path(shutil.which("codex") or "codex")
    proof_root.mkdir(parents=True, exist_ok=True)
    selected_variants = list(variants or default_admission_variants())
    started = time.time()
    case_packets = [
        run_official_mcp_admission_case(
            variant=variant,
            codex_home=codex_home,
            proof_root=proof_root,
            codex_bin=resolved_codex_bin,
            model_id=model_id,
            timeout_seconds=timeout_seconds,
        )
        for variant in selected_variants
    ]
    matrix = build_official_mcp_admission_matrix_packet(case_packets)
    matrix["proof_root"] = str(proof_root)
    matrix["duration_seconds"] = round(time.time() - started, 3)
    matrix["codex_bin"] = str(resolved_codex_bin)
    matrix["codex_model_id"] = model_id
    matrix["codex_home_is_operator_supplied"] = True
    matrix["runner_auth_files_read"] = False
    (proof_root / "matrix-packet.json").write_text(
        json.dumps(matrix, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return matrix


def run_natural_alias_intent_matrix(
    *,
    codex_home: Path,
    proof_root: Path,
    codex_bin: Path | None = None,
    model_id: str = DEFAULT_CODEX_MODEL_ID,
    variants: Sequence[OfficialMcpAdmissionVariant] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    resolved_codex_bin = codex_bin or Path(shutil.which("codex") or "codex")
    proof_root.mkdir(parents=True, exist_ok=True)
    selected_variants = list(variants or default_natural_alias_intent_variants())
    started = time.time()
    case_packets = [
        run_official_mcp_admission_case(
            variant=variant,
            codex_home=codex_home,
            proof_root=proof_root,
            codex_bin=resolved_codex_bin,
            model_id=model_id,
            timeout_seconds=timeout_seconds,
        )
        for variant in selected_variants
    ]
    matrix = build_natural_alias_intent_matrix_packet(case_packets)
    matrix["proof_root"] = str(proof_root)
    matrix["duration_seconds"] = round(time.time() - started, 3)
    matrix["codex_bin"] = str(resolved_codex_bin)
    matrix["codex_model_id"] = model_id
    matrix["codex_home_is_operator_supplied"] = True
    matrix["runner_auth_files_read"] = False
    (proof_root / "natural-matrix-packet.json").write_text(
        json.dumps(matrix, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return matrix


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the official Codex MCP admission proof matrix."
    )
    parser.add_argument(
        "--mode",
        choices=("official", "natural"),
        default="official",
    )
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--proof-root", required=True, type=Path)
    parser.add_argument("--codex-bin", default=None, type=Path)
    parser.add_argument("--model", default=DEFAULT_CODEX_MODEL_ID)
    parser.add_argument("--timeout-seconds", default=DEFAULT_TIMEOUT_SECONDS, type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.mode == "natural":
        packet = run_natural_alias_intent_matrix(
            codex_home=args.codex_home,
            proof_root=args.proof_root,
            codex_bin=args.codex_bin,
            model_id=args.model,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        packet = run_official_mcp_admission_matrix(
            codex_home=args.codex_home,
            proof_root=args.proof_root,
            codex_bin=args.codex_bin,
            model_id=args.model,
            timeout_seconds=args.timeout_seconds,
        )
    print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
    return 0 if packet.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
