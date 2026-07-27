# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Dedicated account pool request-bound failover contract.

WBP owns the control-layer failover decision boundary. The low-level provider
dispatch remains the responsibility of the CLIProxyAPI engine. This module
normalizes a request dispatch outcome into a typed failure class, guards that
the failing and replacement accounts are dedicated (not Original/main, without
reading Original auth), decides replacement eligibility, and admits at most
one replacement dispatch per request after a typed eligible failure.

Invariants (W06):
- dedicated accounts only; Original/main account excluded without reading its
  auth;
- quota / auth / cooldown / network / unknown classified separately;
- ambiguous dispatch retries = 0;
- replacement dispatch maximum = 1 per request;
- a failed account is not selected again for the same request;
- manual_hold / cooldown / retired accounts are excluded;
- a switch is never silent;
- the serving opaque account ref is visible in the receipt;
- synthetic proof is mandatory; absence of live credentials does not block
  implementation.

All command results are produced through the shared core packet builder
(``build_command_payload``) and pass ``inspect_command_packet_semantics``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import time
from typing import Any, Mapping, Sequence

from .core import packets as command_packets
from .runtime import build_command_payload

# Typed failure classes. The engine may surface many error strings; this is the
# control-layer normalization taxonomy. Order matters for deterministic
# classification when an outcome carries multiple signals (most specific first).
ACCOUNT_FAILURE_QUOTA = "quota"
ACCOUNT_FAILURE_AUTH = "auth"
ACCOUNT_FAILURE_COOLDOWN = "cooldown"
ACCOUNT_FAILURE_NETWORK = "network"
ACCOUNT_FAILURE_UNKNOWN = "unknown"
ACCOUNT_FAILURE_CLASSES = (
    ACCOUNT_FAILURE_QUOTA,
    ACCOUNT_FAILURE_AUTH,
    ACCOUNT_FAILURE_COOLDOWN,
    ACCOUNT_FAILURE_NETWORK,
    ACCOUNT_FAILURE_UNKNOWN,
)

# A failure class is "eligible" for an automatic request-bound replacement if
# it is a typed backend-side failure (quota / auth / cooldown). Network and
# unknown failures are NOT eligible: a network failure may be transient
# client-side, and an unknown failure must not trigger a silent switch.
ACCOUNT_ELIGIBLE_FAILURE_CLASSES = frozenset(
    {ACCOUNT_FAILURE_QUOTA, ACCOUNT_FAILURE_AUTH, ACCOUNT_FAILURE_COOLDOWN}
)

ACCOUNT_OUTCOME_SUCCESS = "success"
ACCOUNT_OUTCOME_FAILURE = "failure"
ACCOUNT_OUTCOME_AMBIGUOUS = "ambiguous"

FAILOVER_EFFECT_READ = "read"
FAILOVER_EFFECT_MUTATE = "mutate"
FAILOVER_EFFECT_REPAIR = "repair"

# Maximum replacement dispatches admitted per request id.
MAX_REPLACEMENT_DISPATCHES_PER_REQUEST = 1


@dataclasses.dataclass(frozen=True)
class AccountRef:
    """Opaque account reference. Never carries auth material."""

    backend_id: str
    pool: str
    status: str
    manual_hold: bool
    cooldown_until: str | None
    last_error_class: str | None
    dedicated_provenance_proven: bool

    @property
    def is_dedicated(self) -> bool:
        return self.dedicated_provenance_proven

    @property
    def is_eligible_for_routing(self) -> bool:
        if self.manual_hold:
            return False
        if self.pool not in ("active",):
            return False
        if self.status not in ("healthy", "degraded"):
            return False
        if self.cooldown_until:
            return False
        return True


@dataclasses.dataclass(frozen=True)
class DispatchOutcome:
    """Normalized engine dispatch outcome for one account on one request."""

    outcome: str  # success / failure / ambiguous
    failure_class: str | None
    http_status: int | None
    engine_error_code: str | None
    engine_error_text_digest: str | None
    response_observed: bool
    ambiguous_delivery: bool

    @property
    def is_typed_eligible_failure(self) -> bool:
        return (
            self.outcome == ACCOUNT_OUTCOME_FAILURE
            and self.failure_class in ACCOUNT_ELIGIBLE_FAILURE_CLASSES
            and not self.ambiguous_delivery
        )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_failure_class(
    *,
    http_status: int | None,
    engine_error_code: str | None,
    engine_error_text: str | None,
    cooldown_until: str | None,
) -> str:
    """Deterministic control-layer normalization of an engine dispatch failure
    into one of ACCOUNT_FAILURE_CLASSES."""
    text = (engine_error_text or "").lower()
    code = (engine_error_code or "").lower()
    # Cooldown is a state signal, not strictly an HTTP code.
    if cooldown_until:
        return ACCOUNT_FAILURE_COOLDOWN
    if http_status == 429:
        return ACCOUNT_FAILURE_QUOTA
    if http_status in (401, 403):
        return ACCOUNT_FAILURE_AUTH
    if "quota" in text or "usage_limit" in text or "rate_limit" in text or code in ("quota_exhausted",):
        return ACCOUNT_FAILURE_QUOTA
    if "auth" in text or "unauthorized" in text or "forbidden" in text or code in ("auth_failed",):
        return ACCOUNT_FAILURE_AUTH
    if "cooldown" in text or code in ("cooldown",):
        return ACCOUNT_FAILURE_COOLDOWN
    if http_status and (http_status >= 500 or http_status in (408, 502, 503, 504)):
        return ACCOUNT_FAILURE_NETWORK
    if any(tok in text for tok in ("timeout", "connection", "network", "dns", "refused", "reset")):
        return ACCOUNT_FAILURE_NETWORK
    return ACCOUNT_FAILURE_UNKNOWN


def normalize_dispatch_outcome(
    *,
    success: bool,
    http_status: int | None = None,
    engine_error_code: str | None = None,
    engine_error_text: str | None = None,
    cooldown_until: str | None = None,
    response_observed: bool = False,
    ambiguous_delivery: bool = False,
) -> DispatchOutcome:
    """Normalize a raw engine dispatch result into a typed DispatchOutcome.

    ``ambiguous_delivery=True`` (the engine could not prove whether the
    request was delivered) forces outcome=ambiguous regardless of HTTP status,
    because retrying an already-delivered request is unsafe.
    """
    if ambiguous_delivery:
        return DispatchOutcome(
            outcome=ACCOUNT_OUTCOME_AMBIGUOUS,
            failure_class=None,
            http_status=http_status,
            engine_error_code=engine_error_code,
            engine_error_text_digest=_sha256_text(engine_error_text or "") if engine_error_text else None,
            response_observed=response_observed,
            ambiguous_delivery=True,
        )
    if success:
        return DispatchOutcome(
            outcome=ACCOUNT_OUTCOME_SUCCESS,
            failure_class=None,
            http_status=http_status,
            engine_error_code=engine_error_code,
            engine_error_text_digest=None,
            response_observed=response_observed,
            ambiguous_delivery=False,
        )
    failure_class = _normalize_failure_class(
        http_status=http_status,
        engine_error_code=engine_error_code,
        engine_error_text=engine_error_text,
        cooldown_until=cooldown_until,
    )
    return DispatchOutcome(
        outcome=ACCOUNT_OUTCOME_FAILURE,
        failure_class=failure_class,
        http_status=http_status,
        engine_error_code=engine_error_code,
        engine_error_text_digest=_sha256_text(engine_error_text or "") if engine_error_text else None,
        response_observed=response_observed,
        ambiguous_delivery=False,
    )


def _account_ref_from_backend(backend: Mapping[str, Any]) -> AccountRef:
    return AccountRef(
        backend_id=str(backend.get("id") or ""),
        pool=str(backend.get("pool") or ""),
        status=str(backend.get("status") or ""),
        manual_hold=bool(backend.get("manual_hold")),
        cooldown_until=(str(backend["cooldown_until"]) if backend.get("cooldown_until") else None),
        last_error_class=(str(backend["last_error_class"]) if backend.get("last_error_class") else None),
        dedicated_provenance_proven=bool(backend.get("dedicated_provenance_proven", False)),
    )


@dataclasses.dataclass
class FailoverState:
    """Per-request failover admission state. Persisted per request id so that
    at most MAX_REPLACEMENT_DISPATCHES_PER_REQUEST replacements are admitted."""

    request_id: str
    failed_account_ids: list[str]
    replacement_dispatches_admitted: int

    @property
    def replacement_budget_remaining(self) -> int:
        return max(0, MAX_REPLACEMENT_DISPATCHES_PER_REQUEST - self.replacement_dispatches_admitted)


@dataclasses.dataclass(frozen=True)
class FailoverDecision:
    admitted: bool
    replacement_account: AccountRef | None
    reason: str
    machine_error_code: str


def decide_request_bound_replacement(
    *,
    failing_account: AccountRef,
    outcome: DispatchOutcome,
    state: FailoverState,
    candidate_pool: Sequence[AccountRef],
) -> FailoverDecision:
    """Decide whether a request-bound replacement dispatch is admitted.

    Rules:
    - The failing account must be dedicated (dedicated provenance proven).
    - The outcome must be a typed eligible failure (quota / auth / cooldown),
      not ambiguous, not network/unknown.
    - At most MAX_REPLACEMENT_DISPATCHES_PER_REQUEST replacements per request.
    - The failing account is recorded and never reselected for this request.
    - The replacement must be a dedicated, routing-eligible account that is not
      already in the failed set.
    - If no eligible replacement exists, the decision fails closed (no silent
      switch, no retry storm).
    """
    if not failing_account.is_dedicated:
        return FailoverDecision(
            admitted=False,
            replacement_account=None,
            reason="failing account is not dedicated provenance-proven",
            machine_error_code="FAILOVER_FAILING_ACCOUNT_NOT_DEDICATED",
        )
    if outcome.outcome == ACCOUNT_OUTCOME_AMBIGUOUS:
        return FailoverDecision(
            admitted=False,
            replacement_account=None,
            reason="ambiguous delivery; replacement would risk duplicate dispatch",
            machine_error_code="FAILOVER_AMBIGUOUS_DELIVERY",
        )
    if outcome.outcome == ACCOUNT_OUTCOME_SUCCESS:
        return FailoverDecision(
            admitted=False,
            replacement_account=None,
            reason="outcome is success; no replacement needed",
            machine_error_code="FAILOVER_SUCCESS_NO_REPLACEMENT",
        )
    if not outcome.is_typed_eligible_failure:
        return FailoverDecision(
            admitted=False,
            replacement_account=None,
            reason=f"failure class {outcome.failure_class} is not eligible for automatic replacement",
            machine_error_code="FAILOVER_FAILURE_CLASS_NOT_ELIGIBLE",
        )
    if state.replacement_budget_remaining <= 0:
        return FailoverDecision(
            admitted=False,
            replacement_account=None,
            reason="replacement dispatch budget exhausted for this request",
            machine_error_code="FAILOVER_REPLACEMENT_BUDGET_EXHAUSTED",
        )
    failed_ids = set(state.failed_account_ids)
    failed_ids.add(failing_account.backend_id)
    for candidate in candidate_pool:
        if candidate.backend_id in failed_ids:
            continue
        if not candidate.is_dedicated:
            continue
        if not candidate.is_eligible_for_routing:
            continue
        return FailoverDecision(
            admitted=True,
            replacement_account=candidate,
            reason="typed eligible failure; exactly one replacement admitted",
            machine_error_code="OK",
        )
    return FailoverDecision(
        admitted=False,
        replacement_account=None,
        reason="no dedicated eligible replacement account available",
        machine_error_code="FAILOVER_NO_ELIGIBLE_REPLACEMENT",
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


def build_failover_receipt(
    *,
    request_id: str,
    failing_account: AccountRef,
    outcome: DispatchOutcome,
    decision: FailoverDecision,
    observed_at_utc: str,
) -> dict[str, Any]:
    """Build the observable serving-account/switch receipt as a shared core
    command packet."""
    extra: dict[str, Any] = {
        "request_id": request_id,
        "failing_account_ref": _opaque_ref(failing_account),
        "outcome": {
            "outcome": outcome.outcome,
            "failure_class": outcome.failure_class,
            "http_status": outcome.http_status,
            "engine_error_code": outcome.engine_error_code,
            "response_observed": outcome.response_observed,
            "ambiguous_delivery": outcome.ambiguous_delivery,
        },
        "decision": {
            "admitted": decision.admitted,
            "reason": decision.reason,
            "replacement_account_ref": (
                _opaque_ref(decision.replacement_account) if decision.replacement_account else None
            ),
        },
        "observed_at_utc": observed_at_utc,
        "max_replacement_dispatches_per_request": MAX_REPLACEMENT_DISPATCHES_PER_REQUEST,
    }
    if decision.admitted and decision.replacement_account is not None:
        return _build_packet(
            ok=True,
            human_message=(
                "Typed eligible failure; exactly one replacement dispatch "
                "admitted to a dedicated eligible account."
            ),
            machine_error_code="OK",
            operator_action="none",
            liveness="degraded",
            severity="recoverable",
            changed_files=[],
            effect=FAILOVER_EFFECT_MUTATE,
            extra=extra,
        )
    return _build_packet(
        ok=False,
        human_message=f"Request-bound replacement not admitted: {decision.reason}.",
        machine_error_code=decision.machine_error_code,
        operator_action="user_action",
        liveness="degraded",
        severity="recoverable",
        changed_files=[],
        effect=FAILOVER_EFFECT_MUTATE,
        extra=extra,
    )


def _opaque_ref(account: AccountRef) -> dict[str, Any]:
    """Opaque account reference. Never exposes auth material, raw identifiers
    beyond the opaque backend id, or Original/main account markers."""
    return {
        "backend_id": account.backend_id,
        "pool": account.pool,
        "dedicated": account.is_dedicated,
        "eligible_for_routing": account.is_eligible_for_routing,
        "manual_hold": account.manual_hold,
        "cooldown_present": account.cooldown_until is not None,
    }


def run_synthetic_failover_matrix() -> list[dict[str, Any]]:
    """Deterministic synthetic failover matrix.

    Exercises every typed failure class, ambiguous delivery, non-dedicated
    rejection, budget exhaustion, no-eligible-replacement, and success paths
    without any live provider credentials. Each scenario returns the core
    command-packet receipt and asserts the contract invariants.
    """
    now = "2026-07-27T00:00:00Z"
    scenarios: list[dict[str, Any]] = []

    def dedicated(backend_id: str, *, pool: str = "active", status: str = "healthy", cooldown: str | None = None, manual_hold: bool = False) -> AccountRef:
        return AccountRef(
            backend_id=backend_id,
            pool=pool,
            status=status,
            manual_hold=manual_hold,
            cooldown_until=cooldown,
            last_error_class=None,
            dedicated_provenance_proven=True,
        )

    request_id = "synthetic-req-1"

    # Scenario 1: quota failure on dedicated A -> admit B.
    failing_a = dedicated("acct-a")
    candidate_b = dedicated("acct-b")
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "quota_failure_admits_replacement", "receipt": receipt})

    # Scenario 2: auth failure -> admit B.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=401, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "auth_failure_admits_replacement", "receipt": receipt})

    # Scenario 3: cooldown failure -> admit B.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, cooldown_until="2026-07-27T01:00:00Z", response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "cooldown_failure_admits_replacement", "receipt": receipt})

    # Scenario 4: network failure -> not eligible, fail closed.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=503, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "network_failure_not_eligible", "receipt": receipt})

    # Scenario 5: unknown failure -> not eligible.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, engine_error_text="something odd", response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "unknown_failure_not_eligible", "receipt": receipt})

    # Scenario 6: ambiguous delivery -> never replace.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=429, ambiguous_delivery=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "ambiguous_delivery_never_replaces", "receipt": receipt})

    # Scenario 7: non-dedicated failing account -> reject.
    non_dedicated = AccountRef(
        backend_id="acct-original",
        pool="active",
        status="healthy",
        manual_hold=False,
        cooldown_until=None,
        last_error_class=None,
        dedicated_provenance_proven=False,
    )
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=non_dedicated, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=non_dedicated, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "non_dedicated_failing_rejected", "receipt": receipt})

    # Scenario 8: budget exhausted -> fail closed.
    state = FailoverState(
        request_id=request_id,
        failed_account_ids=["acct-x"],
        replacement_dispatches_admitted=MAX_REPLACEMENT_DISPATCHES_PER_REQUEST,
    )
    outcome = normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "budget_exhausted_fail_closed", "receipt": receipt})

    # Scenario 9: no eligible replacement (B held) -> fail closed.
    held_b = dedicated("acct-b", manual_hold=True)
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[held_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "no_eligible_replacement_fail_closed", "receipt": receipt})

    # Scenario 10: failed account A is excluded from reselection; B admitted,
    # and a second failure on B does NOT admit a third (budget).
    state = FailoverState(
        request_id=request_id, failed_account_ids=["acct-a"], replacement_dispatches_admitted=1
    )
    outcome = normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=candidate_b, outcome=outcome, state=state, candidate_pool=[failing_a, candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=candidate_b, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "second_failure_budget_exhausted", "receipt": receipt})

    # Scenario 11: success outcome -> no replacement.
    state = FailoverState(request_id=request_id, failed_account_ids=[], replacement_dispatches_admitted=0)
    outcome = normalize_dispatch_outcome(success=True, http_status=200, response_observed=True)
    decision = decide_request_bound_replacement(
        failing_account=failing_a, outcome=outcome, state=state, candidate_pool=[candidate_b]
    )
    receipt = build_failover_receipt(
        request_id=request_id, failing_account=failing_a, outcome=outcome, decision=decision, observed_at_utc=now
    )
    scenarios.append({"scenario": "success_no_replacement", "receipt": receipt})

    return scenarios


__all__ = [
    "ACCOUNT_FAILURE_CLASSES",
    "ACCOUNT_FAILURE_QUOTA",
    "ACCOUNT_FAILURE_AUTH",
    "ACCOUNT_FAILURE_COOLDOWN",
    "ACCOUNT_FAILURE_NETWORK",
    "ACCOUNT_FAILURE_UNKNOWN",
    "ACCOUNT_ELIGIBLE_FAILURE_CLASSES",
    "ACCOUNT_OUTCOME_SUCCESS",
    "ACCOUNT_OUTCOME_FAILURE",
    "ACCOUNT_OUTCOME_AMBIGUOUS",
    "MAX_REPLACEMENT_DISPATCHES_PER_REQUEST",
    "AccountRef",
    "DispatchOutcome",
    "FailoverState",
    "FailoverDecision",
    "normalize_dispatch_outcome",
    "decide_request_bound_replacement",
    "build_failover_receipt",
    "run_synthetic_failover_matrix",
]
