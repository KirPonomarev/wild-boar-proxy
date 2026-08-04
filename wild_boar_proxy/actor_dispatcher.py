# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic fail-closed actor dispatcher (B05).

Resolves alias -> slot binding -> actor -> role assignment -> context digest,
computes the effective permission as the intersection of the binding
permission ceiling, the explicit operator grant, the adapter capability, and
the runtime policy, and produces a dispatch plan bound to exact identities.

No provider call happens here: dispatch execution is owned by the transport
adapters (B07/B08) and the workflow runner (B13). An unavailable actor never
returns another actor's response under the original identity, and
cross-provider fallback is off by default.
"""

from __future__ import annotations

from typing import Any, Mapping

from .actor_registry import (
    ALLOWED_PERMISSION_CEILINGS,
    CONTEXT_POLICY_CONTINUE,
    CONTEXT_POLICY_FORK,
    CONTEXT_POLICY_FRESH,
    FORBIDDEN_STALE_ROUTE_IDS,
    PRIMARY_SLOT_ID,
    resolve_binding_reference,
    validate_actor_registry_document,
)

PERMISSION_NONE = "none"
from .transport_normalization import (
    ERR_CAPABILITY_NOT_ADMITTED,
    NormalizedRequest,
    TransportError,
    normalize_request,
)

PERMISSION_NONE = "none"

# Capability-set model: permissions form two capability trees rooted at
# context_only (repo axis and external axis). Linear ranking collapses
# incompatible capabilities (network_read vs repo_write) — we must use
# set intersection instead.
CAPABILITY_SETS = {
    PERMISSION_NONE: frozenset(),
    "context_only": frozenset({"context_only"}),
    "repo_read": frozenset({"context_only", "repo_read"}),
    "repo_write": frozenset({"context_only", "repo_read", "repo_write"}),
    "browser_read": frozenset({"context_only", "browser_read"}),
    "network_read": frozenset({"context_only", "network_read"}),
}

# Ordered from most-specific to least: the first permission whose capability
# set is a subset of the effective set is the most-specific granted capability.
_PERMISSION_SPECIFICITY = (
    "repo_write",
    "repo_read",
    "network_read",
    "browser_read",
    "context_only",
    PERMISSION_NONE,
)

# Legacy compatibility rank for callers that still expect ordering.
PERMISSION_ORDER = {
    PERMISSION_NONE: 0,
    "context_only": 1,
    "repo_read": 2,
    "repo_write": 3,
    "browser_read": 4,
    "network_read": 5,
}


def _intersect_permissions(*permissions: str) -> str:
    """Intersect permission surfaces as capability sets, not a linear rank.

    network_read and repo_write are independent axes: their intersection is
    context_only, never repo_write.
    """
    sets = [CAPABILITY_SETS.get(p, frozenset()) for p in permissions]
    if not sets or not all(sets):
        return PERMISSION_NONE
    effective = sets[0]
    for s in sets[1:]:
        effective = effective & s
    for perm in _PERMISSION_SPECIFICITY:
        if CAPABILITY_SETS[perm].issubset(effective):
            return perm
    return PERMISSION_NONE


def effective_permission(
    *,
    binding_permission_ceiling: str,
    explicit_operator_grant: str,
    adapter_capability: str,
    runtime_policy: str,
) -> str:
    """effective_permission = intersection of all four surfaces.

    Assignment and role can only request or reduce permission; they never
    grant it.
    """
    return _intersect_permissions(
        binding_permission_ceiling,
        explicit_operator_grant,
        adapter_capability,
        runtime_policy,
    )


class DispatchResolutionError(Exception):
    def __init__(self, machine_error_code: str, message: str) -> None:
        super().__init__(message)
        self.machine_error_code = machine_error_code


def _resolve_registry(
    registry_document: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the validated registry document or raise."""
    if registry_document is None:
        raise DispatchResolutionError(
            "ACTOR_REGISTRY_UNAVAILABLE", "actor registry document is unavailable"
        )
    validation = validate_actor_registry_document(registry_document)
    if not validation["valid"]:
        raise DispatchResolutionError(
            "ACTOR_REGISTRY_INVALID", ";".join(validation["reasons"])
        )
    return dict(registry_document)


def _legacy_binding_for_alias(
    legacy_bindings: list[dict[str, Any]],
    alias: str,
) -> dict[str, Any]:
    key = str(alias).strip().casefold()
    for binding in legacy_bindings:
        if key in {str(a).strip().casefold() for a in (binding.get("aliases") or [])}:
            return dict(binding)
    return {}


def resolve_alias_dispatch(
    *,
    alias: str,
    registry_document: Mapping[str, Any] | None = None,
    legacy_bindings: list[dict[str, Any]] | None = None,
    explicit_operator_grant: str = "context_only",
    adapter_capability: str = "context_only",
    runtime_policy: str = "repo_read",
    context_digest: str = "",
    requested_permission: str = "context_only",
) -> dict[str, Any]:
    """Resolve an addressed alias into a bounded dispatch plan.

    Resolution order: canonical registry (slot binding -> actor -> assignment)
    first; legacy v1 bindings are a wire-compatible fallback that is
    explicitly reported as ``legacy_projection_used``. Unknown aliases,
    binding/assignment/context drift, permission denial, and stale routes fail
    closed.
    """
    alias_text = str(alias or "").strip()
    if not alias_text:
        raise DispatchResolutionError("ALIAS_EMPTY", "alias must not be empty")

    reference: dict[str, Any] = {}
    legacy_used = False
    binding: dict[str, Any] = {}
    actor: dict[str, Any] = {}
    assignment: dict[str, Any] = {}

    def _resolve_legacy() -> None:
        nonlocal legacy_used, binding
        legacy_used = True
        legacy = _legacy_binding_for_alias(legacy_bindings or [], alias_text)
        if not legacy:
            raise DispatchResolutionError("ALIAS_UNKNOWN", f"alias not bound: {alias_text}")
        route_id = str(legacy.get("route_id") or "")
        if route_id in FORBIDDEN_STALE_ROUTE_IDS:
            raise DispatchResolutionError("STALE_ROUTE_REJECTED", route_id)
        binding = legacy

    if registry_document is not None:
        _resolve_registry(registry_document)
        reference = resolve_binding_reference(registry_document, alias=alias_text)
        if reference:
            actors = [a for a in registry_document.get("actors", []) if isinstance(a, dict)]
            bindings = [
                b for b in registry_document.get("slot_bindings", []) if isinstance(b, dict)
            ]
            assignments = [
                a for a in registry_document.get("role_assignments", []) if isinstance(a, dict)
            ]
            binding = next(
                (
                    b for b in bindings
                    if str(b.get("binding_id") or "") == str(reference.get("binding_id") or "")
                ),
                {},
            )
            actor = next(
                (a for a in actors if str(a.get("actor_id") or "") == str(binding.get("actor_id") or "")),
                {},
            )
            assignment = next(
                (
                    a for a in assignments
                    if str(a.get("assignment_id") or "") == str(reference.get("assignment_id") or "")
                ),
                {},
            )
        else:
            _resolve_legacy()
    else:
        _resolve_legacy()

    if not binding:
        raise DispatchResolutionError("BINDING_UNRESOLVED", f"no binding for alias: {alias_text}")
    # Disabled actor must never dispatch.
    if actor and actor.get("enabled") is False:
        raise DispatchResolutionError(
            "ACTOR_DISABLED", f"actor '{actor.get('actor_id')}' is disabled"
        )
    # Disabled binding must never dispatch.
    if binding.get("enabled") is False:
        raise DispatchResolutionError(
            "BINDING_DISABLED", f"binding '{binding.get('binding_id')}' is disabled"
        )
    if not actor and not legacy_used:
        raise DispatchResolutionError("ACTOR_UNRESOLVED", "actor definition missing for binding")
    if not legacy_used and not assignment:
        raise DispatchResolutionError("ASSIGNMENT_UNRESOLVED", "role assignment missing for binding")

    binding_ceiling = (
        str(actor.get("permission_ceiling") or PERMISSION_NONE)
        if actor
        else ("context_only" if legacy_used else PERMISSION_NONE)
    )
    if binding_ceiling not in ALLOWED_PERMISSION_CEILINGS:
        binding_ceiling = PERMISSION_NONE
    permission = effective_permission(
        binding_permission_ceiling=binding_ceiling,
        explicit_operator_grant=explicit_operator_grant,
        adapter_capability=adapter_capability,
        runtime_policy=runtime_policy,
    )
    if PERMISSION_ORDER.get(requested_permission, 0) > PERMISSION_ORDER.get(permission, 0):
        raise DispatchResolutionError(
            "PERMISSION_DENIED",
            f"requested {requested_permission} exceeds effective {permission}",
        )
    # Capability-set check: requested capabilities must be a subset of
    # effective capabilities. Cross-axis requests (e.g. browser_read when
    # effective is network_read) must fail even if linear rank allows it.
    requested_caps = CAPABILITY_SETS.get(requested_permission, frozenset())
    effective_caps = CAPABILITY_SETS.get(permission, frozenset())
    if not requested_caps.issubset(effective_caps):
        raise DispatchResolutionError(
            "PERMISSION_DENIED",
            f"requested capability {requested_permission} ({requested_caps}) "
            f"is not a subset of effective {permission} ({effective_caps})",
        )
    context_policy = (
        str(assignment.get("assignment_context_policy") or CONTEXT_POLICY_FRESH)
        if assignment
        else CONTEXT_POLICY_FRESH
    )
    if context_policy not in {CONTEXT_POLICY_CONTINUE, CONTEXT_POLICY_FRESH, CONTEXT_POLICY_FORK}:
        raise DispatchResolutionError("CONTEXT_POLICY_UNKNOWN", context_policy)
    if context_policy == CONTEXT_POLICY_FORK and not context_digest:
        raise DispatchResolutionError("FORK_CONTEXT_DIGEST_MISSING", "fork requires an exact context digest")

    plan: dict[str, Any] = {
        "status": "ok",
        "exit_code": 0,
        "machine_error_code": "DISPATCH_PLAN_READY",
        "changed_files": [],
        "next_action": "none",
        "liveness": "healthy",
        "severity": "recoverable",
        "operator_action": "none",
        "alias": alias_text,
        "legacy_projection_used": legacy_used,
        "slot_id": str(binding.get("slot_id") or ""),
        "binding_id": str(binding.get("binding_id") or ""),
        "binding_revision": binding.get("binding_revision"),
        "assignment_id": str(assignment.get("assignment_id") or ""),
        "assignment_revision": assignment.get("assignment_revision"),
        "actor_id": str(binding.get("actor_id") or binding.get("agent_id") or ""),
        "transport_adapter_id": str(actor.get("transport_adapter_id") or ""),
        "provider_id": str(actor.get("provider_id") or ""),
        "route_id": str(binding.get("route_id") or ""),
        "model_policy": actor.get("model_policy") or {},
        "assignment_context_policy": context_policy,
        "effective_permission": permission,
        "binding_permission_ceiling": binding_ceiling,
        "explicit_operator_grant": explicit_operator_grant,
        "adapter_capability": adapter_capability,
        "runtime_policy": runtime_policy,
        "requested_permission": requested_permission,
        "context_digest": context_digest,
        "no_fallback": True,
        "cross_provider_fallback": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    return plan


def build_dispatch_request(
    *,
    dispatch_plan: Mapping[str, Any],
    dispatch_id: str,
    text: str,
    idempotency_key: str,
    context_digest: str = "",
) -> NormalizedRequest | TransportError:
    """Build the normalized request envelope from a resolved dispatch plan."""
    if dispatch_plan.get("status") != "ok":
        return TransportError("dispatch_plan_not_ready", "dispatch plan is not ready")
    return normalize_request(
        {
            "dispatch_id": dispatch_id,
            "transport_kind": str(dispatch_plan.get("transport_adapter_id") or ""),
            "provider_id": str(dispatch_plan.get("provider_id") or ""),
            "model_id": str((dispatch_plan.get("model_policy") or {}).get("model_id") or ""),
            "text": text,
            "idempotency_key": idempotency_key,
            "context_digest": context_digest or str(dispatch_plan.get("context_digest") or ""),
            "requested_permission": str(dispatch_plan.get("requested_permission") or ""),
            "effective_permission": str(dispatch_plan.get("effective_permission") or ""),
        }
    )


__all__ = [
    "DispatchResolutionError",
    "effective_permission",
    "resolve_alias_dispatch",
    "build_dispatch_request",
    "PERMISSION_ORDER",
]
