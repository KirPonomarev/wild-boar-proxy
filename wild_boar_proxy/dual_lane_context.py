# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Named dual-lane thread context and delegation contract (W08).

Proves GPT/Codex and Deep/DIP as independent named actors in one visible
Custom Codex thread through a bounded context envelope and a deterministic
delegation packet. The context relay never transfers private chain-of-thought,
raw auth/session/cookie/token, Original profile data, route secrets, or
unbounded repository dumps.

"Allows one visible Custom Codex conversation" means the context envelope
carries only permitted visible-turn metadata, never vendor-native hidden
sessions or private reasoning.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping, Sequence

from .core import packets as command_packets
from .runtime import build_command_payload

LANE_GPT = "custom_native_gpt_lane"
LANE_DEEPSEEK = "deepseek_api_lane"
DUAL_LANES = (LANE_GPT, LANE_DEEPSEEK)

CONTEXT_EFFECT_READ = "read"

# Forbidden context payload tokens: the relay must never carry these.
FORBIDDEN_CONTEXT_TOKENS = (
    "chain_of_thought",
    "private_reasoning",
    "raw_auth",
    "session_cookie",
    "oauth_token",
    "route_secret",
    "api_key",
    "sk-",
    "password",
    "refresh_token",
)


@dataclasses.dataclass(frozen=True)
class VisibleTurn:
    """One permitted visible turn in the shared thread context."""

    actor_label: str  # "GPT" | "Deep"
    turn_kind: str  # "user_request" | "actor_reply" | "delegation"
    content_digest: str  # digest of the visible turn text
    redacted_summary: str  # bounded human-readable summary

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class ContextEnvelope:
    """Bounded context envelope relayed to an API actor.

    Carries only: current operator request, permitted previous visible turns,
    source actor labels, server-issued mode/model/alias/route bindings, and a
    truncation summary. Never carries forbidden tokens.
    """

    current_request_digest: str
    permitted_visible_turns: tuple[VisibleTurn, ...]
    actor_labels: tuple[str, ...]
    server_bindings: dict[str, Any]
    truncation_summary: str
    repo_bridge_admitted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_request_digest": self.current_request_digest,
            "permitted_visible_turns": [t.to_dict() for t in self.permitted_visible_turns],
            "actor_labels": list(self.actor_labels),
            "server_bindings": dict(self.server_bindings),
            "truncation_summary": self.truncation_summary,
            "repo_bridge_admitted": self.repo_bridge_admitted,
        }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _envelope_has_forbidden_tokens(envelope: ContextEnvelope) -> list[str]:
    """Return any forbidden tokens found in the envelope's serialized form."""
    import json

    body = json.dumps(envelope.to_dict())
    found = [tok for tok in FORBIDDEN_CONTEXT_TOKENS if tok.lower() in body.lower()]
    return found


def build_context_envelope(
    *,
    current_request: str,
    permitted_visible_turns: Sequence[VisibleTurn],
    actor_labels: Sequence[str],
    server_bindings: Mapping[str, Any] | None = None,
    repo_bridge_admitted: bool = False,
    max_visible_turns: int = 8,
) -> ContextEnvelope:
    """Build a bounded context envelope. Truncates to max_visible_turns."""
    truncated = tuple(permitted_visible_turns[-max_visible_turns:])
    truncation_summary = (
        f"{len(permitted_visible_turns)} visible turns; relayed {len(truncated)}"
        if len(permitted_visible_turns) > len(truncated)
        else f"{len(truncated)} visible turns relayed"
    )
    return ContextEnvelope(
        current_request_digest=_sha256_text(current_request),
        permitted_visible_turns=truncated,
        actor_labels=tuple(actor_labels),
        server_bindings=dict(server_bindings or {}),
        truncation_summary=truncation_summary,
        repo_bridge_admitted=repo_bridge_admitted,
    )


def validate_context_envelope(envelope: ContextEnvelope) -> list[str]:
    """Validate the envelope never carries forbidden tokens. Returns violations."""
    return _envelope_has_forbidden_tokens(envelope)


@dataclasses.dataclass(frozen=True)
class DelegationContract:
    """Codex -> Deep bounded delegation contract."""

    delegating_lane: str  # LANE_GPT
    delegate_lane: str  # LANE_DEEPSEEK
    bounded_task_digest: str
    repo_bridge_admitted: bool
    delegation_kind: str  # "bounded_work" | "review_request"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def build_delegation_contract(
    *,
    delegating_lane: str,
    delegate_lane: str,
    bounded_task: str,
    repo_bridge_admitted: bool = False,
    delegation_kind: str = "bounded_work",
) -> DelegationContract:
    return DelegationContract(
        delegating_lane=delegating_lane,
        delegate_lane=delegate_lane,
        bounded_task_digest=_sha256_text(bounded_task),
        repo_bridge_admitted=repo_bridge_admitted,
        delegation_kind=delegation_kind,
    )


def _build_packet(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    operator_action: str,
    liveness: str,
    severity: str,
    changed_files: list[str],
    effect: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        operator_action=operator_action,
        liveness=liveness,
        severity=severity,
        changed_files=changed_files,
        effect=effect,
        extra=extra,
    )


def build_context_relay_receipt(
    *,
    envelope: ContextEnvelope,
    target_lane: str,
) -> dict[str, Any]:
    """Build the context relay receipt as a core command packet."""
    violations = validate_context_envelope(envelope)
    extra: dict[str, Any] = {
        "target_lane": target_lane,
        "envelope": envelope.to_dict(),
        "forbidden_token_violations": violations,
    }
    if violations:
        return _build_packet(
            ok=False,
            human_message="Context envelope carries forbidden tokens; relay refused.",
            machine_error_code="CONTEXT_RELAY_FORBIDDEN_TOKENS",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=CONTEXT_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=True,
        human_message=f"Context envelope relayed to {target_lane} without forbidden tokens.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=CONTEXT_EFFECT_READ,
        extra=extra,
    )


def build_delegation_receipt(
    *,
    contract: DelegationContract,
    envelope: ContextEnvelope,
) -> dict[str, Any]:
    """Build the Codex->Deep delegation receipt as a core command packet."""
    violations = validate_context_envelope(envelope)
    extra: dict[str, Any] = {
        "delegation": contract.to_dict(),
        "envelope": envelope.to_dict(),
        "forbidden_token_violations": violations,
    }
    if contract.delegating_lane != LANE_GPT or contract.delegate_lane != LANE_DEEPSEEK:
        return _build_packet(
            ok=False,
            human_message="Delegation lane pair is not GPT->Deep.",
            machine_error_code="DELEGATION_LANE_PAIR_INVALID",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=CONTEXT_EFFECT_READ,
            extra=extra,
        )
    if violations:
        return _build_packet(
            ok=False,
            human_message="Delegation envelope carries forbidden tokens; delegation refused.",
            machine_error_code="DELEGATION_FORBIDDEN_TOKENS",
            operator_action="stop",
            liveness="down",
            severity="high",
            changed_files=[],
            effect=CONTEXT_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=True,
        human_message="Codex->Deep bounded delegation admitted with clean context envelope.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=CONTEXT_EFFECT_READ,
        extra=extra,
    )


def run_dual_lane_synthetic_proof() -> list[dict[str, Any]]:
    """Deterministic four-turn context-continuity + delegation proof.

    Turns:
    1. user -> Deep (task)
    2. Deep -> user (reply)
    3. user -> GPT (review the Deep reply)
    4. GPT -> Deep (bounded delegation: refine)

    Plus a Codex->Deep bounded-work delegation packet and a dummy repo-bridge
    delegation. Every receipt is a core command packet and must pass
    inspect_command_packet_semantics. No private reasoning, no secrets.
    """
    receipts: list[dict[str, Any]] = []

    turn1 = VisibleTurn(
        actor_label="user",
        turn_kind="user_request",
        content_digest=_sha256_text("Deep: implement bounded helper"),
        redacted_summary="user asks Deep to implement a bounded helper",
    )
    turn2 = VisibleTurn(
        actor_label="Deep",
        turn_kind="actor_reply",
        content_digest=_sha256_text("helper draft"),
        redacted_summary="Deep produced a bounded helper draft",
    )
    turn3 = VisibleTurn(
        actor_label="user",
        turn_kind="user_request",
        content_digest=_sha256_text("GPT: review the Deep reply"),
        redacted_summary="user asks GPT to review Deep's draft",
    )
    turn4 = VisibleTurn(
        actor_label="GPT",
        turn_kind="actor_reply",
        content_digest=_sha256_text("review notes"),
        redacted_summary="GPT returned review notes on Deep's draft",
    )

    turns = [turn1, turn2, turn3, turn4]

    # Relay to Deep (turn 1 context).
    env_deep = build_context_envelope(
        current_request="Deep: implement bounded helper",
        permitted_visible_turns=turns[:1],
        actor_labels=["user", "Deep"],
        server_bindings={"mode": "chatgpt_plus_api", "alias": "Deep"},
    )
    receipts.append(build_context_relay_receipt(envelope=env_deep, target_lane=LANE_DEEPSEEK))

    # Relay to GPT (turn 3 context: user asks GPT to review Deep).
    env_gpt = build_context_envelope(
        current_request="GPT: review the Deep reply",
        permitted_visible_turns=turns[:3],
        actor_labels=["user", "Deep", "GPT"],
        server_bindings={"mode": "chatgpt_plus_api", "alias": "Codex"},
    )
    receipts.append(build_context_relay_receipt(envelope=env_gpt, target_lane=LANE_GPT))

    # Codex -> Deep bounded delegation.
    delegation_env = build_context_envelope(
        current_request="Deep: refine the helper per GPT review notes",
        permitted_visible_turns=turns,
        actor_labels=["user", "Deep", "GPT"],
        server_bindings={"mode": "chatgpt_plus_api", "alias": "Deep"},
        repo_bridge_admitted=False,
    )
    delegation = build_delegation_contract(
        delegating_lane=LANE_GPT,
        delegate_lane=LANE_DEEPSEEK,
        bounded_task="refine the helper per GPT review notes",
        repo_bridge_admitted=False,
        delegation_kind="bounded_work",
    )
    receipts.append(build_delegation_receipt(contract=delegation, envelope=delegation_env))

    # Codex -> Deep bounded delegation WITH repo bridge admitted (dummy repo edit).
    delegation_repo = build_delegation_contract(
        delegating_lane=LANE_GPT,
        delegate_lane=LANE_DEEPSEEK,
        bounded_task="apply bounded repo edit via repo bridge",
        repo_bridge_admitted=True,
        delegation_kind="bounded_work",
    )
    delegation_repo_env = build_context_envelope(
        current_request="Deep: apply bounded repo edit via repo bridge",
        permitted_visible_turns=turns,
        actor_labels=["user", "Deep", "GPT"],
        server_bindings={"mode": "chatgpt_plus_api", "alias": "Deep"},
        repo_bridge_admitted=True,
    )
    receipts.append(build_delegation_receipt(contract=delegation_repo, envelope=delegation_repo_env))

    return receipts


def run_dual_lane_synthetic_proof_summary() -> dict[str, Any]:
    """Single core command packet wrapping the dual-lane synthetic proof."""
    receipts = run_dual_lane_synthetic_proof()
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    no_forbidden = all(
        not r["extra"].get("forbidden_token_violations")
        if "extra" in r
        else not r.get("forbidden_token_violations")
        for r in receipts
    )
    # build_command_payload merges extra into top level, so violations are top-level.
    no_forbidden = all(not r.get("forbidden_token_violations") for r in receipts)
    ok = not violations and no_forbidden
    return _build_packet(
        ok=ok,
        human_message=(
            "Dual-lane synthetic proof complete; 4-turn context continuity and "
            "Codex->Deep delegation admitted with clean envelopes."
            if ok
            else "Dual-lane synthetic proof had contract violations."
        ),
        machine_error_code="OK" if ok else "DUAL_LANE_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=CONTEXT_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "lanes": list(DUAL_LANES),
            "packet_violations": violations,
            "no_forbidden_tokens": no_forbidden,
        },
    )


__all__ = [
    "LANE_GPT",
    "LANE_DEEPSEEK",
    "DUAL_LANES",
    "FORBIDDEN_CONTEXT_TOKENS",
    "VisibleTurn",
    "ContextEnvelope",
    "DelegationContract",
    "build_context_envelope",
    "validate_context_envelope",
    "build_delegation_contract",
    "build_context_relay_receipt",
    "build_delegation_receipt",
    "run_dual_lane_synthetic_proof",
    "run_dual_lane_synthetic_proof_summary",
]
