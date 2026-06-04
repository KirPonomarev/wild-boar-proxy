# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


ACCOUNT_LIFECYCLE_POOL_RESERVE = "reserve"
ACCOUNT_LIFECYCLE_POOL_ACTIVE = "active"
ACCOUNT_LIFECYCLE_POOL_RETIRED = "retired"
ACCOUNT_LIFECYCLE_VALID_POOLS = frozenset(
    {
        ACCOUNT_LIFECYCLE_POOL_RESERVE,
        ACCOUNT_LIFECYCLE_POOL_ACTIVE,
        ACCOUNT_LIFECYCLE_POOL_RETIRED,
    }
)

ACCOUNT_LIFECYCLE_STATE_NEW_AUTH = "new_auth"
ACCOUNT_LIFECYCLE_STATE_RESERVE = "reserve"
ACCOUNT_LIFECYCLE_STATE_ACTIVE = "active"
ACCOUNT_LIFECYCLE_STATE_HELD_RESERVE = "held_reserve"
ACCOUNT_LIFECYCLE_STATE_HELD_ACTIVE = "held_active"
ACCOUNT_LIFECYCLE_STATE_RETIRED = "retired"
ACCOUNT_LIFECYCLE_STATE_INVALID_POOL = "invalid_pool"
ACCOUNT_LIFECYCLE_EFFECTIVE_STATES = frozenset(
    {
        ACCOUNT_LIFECYCLE_STATE_RESERVE,
        ACCOUNT_LIFECYCLE_STATE_ACTIVE,
        ACCOUNT_LIFECYCLE_STATE_HELD_RESERVE,
        ACCOUNT_LIFECYCLE_STATE_HELD_ACTIVE,
        ACCOUNT_LIFECYCLE_STATE_RETIRED,
    }
)

ACCOUNT_LIFECYCLE_ACTION_ONBOARD = "onboard"
ACCOUNT_LIFECYCLE_ACTION_PROMOTE = "promote"
ACCOUNT_LIFECYCLE_ACTION_DEMOTE = "demote"
ACCOUNT_LIFECYCLE_ACTION_HOLD = "hold"
ACCOUNT_LIFECYCLE_ACTION_RELEASE = "release"
ACCOUNT_LIFECYCLE_ACTION_RETIRE = "retire"
ACCOUNT_LIFECYCLE_ACTIONS = frozenset(
    {
        ACCOUNT_LIFECYCLE_ACTION_ONBOARD,
        ACCOUNT_LIFECYCLE_ACTION_PROMOTE,
        ACCOUNT_LIFECYCLE_ACTION_DEMOTE,
        ACCOUNT_LIFECYCLE_ACTION_HOLD,
        ACCOUNT_LIFECYCLE_ACTION_RELEASE,
        ACCOUNT_LIFECYCLE_ACTION_RETIRE,
    }
)

ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED = "allowed"
ACCOUNT_LIFECYCLE_TRANSITION_CONDITIONAL = "conditional"
ACCOUNT_LIFECYCLE_TRANSITION_FORBIDDEN = "forbidden"
ACCOUNT_LIFECYCLE_TRANSITION_NOOP = "noop"

ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE = "eligible"
ACCOUNT_LIFECYCLE_PRECONDITION_NEW_AUTH_TO_RESERVE = "new_auth_to_reserve"
ACCOUNT_LIFECYCLE_PRECONDITION_NEW_AUTH_ACTIVE_FORBIDDEN = (
    "new_auth_active_forbidden"
)
ACCOUNT_LIFECYCLE_PRECONDITION_PROMOTION_REQUIRES_PROOF = (
    "promotion_requires_validation_sync_policy"
)
ACCOUNT_LIFECYCLE_PRECONDITION_HELD_RELEASE_REQUIRED = (
    "held_backend_release_required"
)
ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED = "backend_retired"
ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RETIRED = "already_retired"
ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RESERVE = "already_reserve"
ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_HELD = "already_held"
ACCOUNT_LIFECYCLE_PRECONDITION_NOT_ON_HOLD = "not_on_hold"
ACCOUNT_LIFECYCLE_PRECONDITION_INVALID_SOURCE_STATE = "invalid_source_state"
ACCOUNT_LIFECYCLE_PRECONDITION_INVALID_ACTION = "invalid_action"
ACCOUNT_LIFECYCLE_PRECONDITION_NOT_LIFECYCLE_ACTION = "not_lifecycle_action"

ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_HOLD_ELIGIBLE = (
    "eligible_backend_for_hold"
)
ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_RELEASE_ELIGIBLE = (
    "eligible_backend_for_release"
)
ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_INVALID = (
    "invalid_lifecycle_precondition"
)

ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_ELIGIBLE = "eligible_reserve_backend"
ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_BACKEND_ON_HOLD = "backend_on_hold"
ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_NOT_RESERVE = "backend_not_reserve"
ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_INVALID = "invalid_lifecycle_precondition"

ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_ELIGIBLE = (
    "eligible_active_backend_for_demote"
)
ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_BACKEND_HELD = "backend_held"
ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_NOT_ACTIVE = "backend_not_active"
ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_INVALID = "invalid_lifecycle_precondition"

ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_ELIGIBLE_ACTIVE = (
    "eligible_active_backend_for_retire"
)
ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_ELIGIBLE_RESERVE = (
    "eligible_reserve_backend_for_retire"
)
ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_NOT_RETIRABLE = (
    "backend_not_retirable_pool"
)
ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_INVALID = "invalid_lifecycle_precondition"


class AccountLifecyclePaths(Protocol):
    pass


def classify_account_lifecycle_state(pool: str, manual_hold: bool) -> str:
    if pool == ACCOUNT_LIFECYCLE_POOL_RESERVE:
        return (
            ACCOUNT_LIFECYCLE_STATE_HELD_RESERVE
            if manual_hold
            else ACCOUNT_LIFECYCLE_STATE_RESERVE
        )
    if pool == ACCOUNT_LIFECYCLE_POOL_ACTIVE:
        return (
            ACCOUNT_LIFECYCLE_STATE_HELD_ACTIVE
            if manual_hold
            else ACCOUNT_LIFECYCLE_STATE_ACTIVE
        )
    if pool == ACCOUNT_LIFECYCLE_POOL_RETIRED:
        return ACCOUNT_LIFECYCLE_STATE_RETIRED
    return ACCOUNT_LIFECYCLE_STATE_INVALID_POOL


def classify_account_lifecycle_transition(
    source_state: str, requested_action: str
) -> dict[str, Any]:
    base = {
        "source_state": source_state,
        "requested_action": requested_action,
        "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_FORBIDDEN,
        "target_state": "",
        "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_INVALID_ACTION,
        "terminal": source_state == ACCOUNT_LIFECYCLE_STATE_RETIRED,
        "return_path_allowed": source_state != ACCOUNT_LIFECYCLE_STATE_RETIRED,
        "requires_validation_sync_policy": False,
    }
    if requested_action not in ACCOUNT_LIFECYCLE_ACTIONS:
        return base
    if source_state not in ACCOUNT_LIFECYCLE_EFFECTIVE_STATES | {
        ACCOUNT_LIFECYCLE_STATE_NEW_AUTH
    }:
        return {
            **base,
            "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_INVALID_SOURCE_STATE,
        }
    if source_state == ACCOUNT_LIFECYCLE_STATE_NEW_AUTH:
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_ONBOARD:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
                "target_state": ACCOUNT_LIFECYCLE_STATE_RESERVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_NEW_AUTH_TO_RESERVE,
            }
        return {
            **base,
            "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_NEW_AUTH_ACTIVE_FORBIDDEN,
        }
    if source_state == ACCOUNT_LIFECYCLE_STATE_RETIRED:
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_RETIRE:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_NOOP,
                "target_state": ACCOUNT_LIFECYCLE_STATE_RETIRED,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RETIRED,
            }
        return {
            **base,
            "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED,
        }
    if requested_action == ACCOUNT_LIFECYCLE_ACTION_RETIRE:
        return {
            **base,
            "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
            "target_state": ACCOUNT_LIFECYCLE_STATE_RETIRED,
            "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE,
        }
    if source_state in {
        ACCOUNT_LIFECYCLE_STATE_HELD_RESERVE,
        ACCOUNT_LIFECYCLE_STATE_HELD_ACTIVE,
    }:
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_RELEASE:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
                "target_state": ACCOUNT_LIFECYCLE_STATE_RESERVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_HOLD:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_NOOP,
                "target_state": source_state,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_HELD,
            }
        return {
            **base,
            "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_HELD_RELEASE_REQUIRED,
        }
    if source_state == ACCOUNT_LIFECYCLE_STATE_RESERVE:
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_PROMOTE:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_CONDITIONAL,
                "target_state": ACCOUNT_LIFECYCLE_STATE_ACTIVE,
                "precondition_status": (
                    ACCOUNT_LIFECYCLE_PRECONDITION_PROMOTION_REQUIRES_PROOF
                ),
                "requires_validation_sync_policy": True,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_HOLD:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
                "target_state": ACCOUNT_LIFECYCLE_STATE_HELD_RESERVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_DEMOTE:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_NOOP,
                "target_state": ACCOUNT_LIFECYCLE_STATE_RESERVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RESERVE,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_RELEASE:
            return {
                **base,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_NOT_ON_HOLD,
            }
    if source_state == ACCOUNT_LIFECYCLE_STATE_ACTIVE:
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_DEMOTE:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
                "target_state": ACCOUNT_LIFECYCLE_STATE_RESERVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_HOLD:
            return {
                **base,
                "transition_status": ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED,
                "target_state": ACCOUNT_LIFECYCLE_STATE_HELD_ACTIVE,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_ELIGIBLE,
            }
        if requested_action == ACCOUNT_LIFECYCLE_ACTION_RELEASE:
            return {
                **base,
                "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_NOT_ON_HOLD,
            }
    return {
        **base,
        "precondition_status": ACCOUNT_LIFECYCLE_PRECONDITION_NOT_LIFECYCLE_ACTION,
    }


def classify_protective_lifecycle_precondition(
    pool: str, manual_hold: bool, action: str
) -> dict[str, Any]:
    effective_state = classify_account_lifecycle_state(pool, manual_hold)
    transition = classify_account_lifecycle_transition(effective_state, action)
    protective_status = ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_INVALID

    transition_precondition = str(transition["precondition_status"])

    if transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED:
        protective_status = ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED
    elif (
        action == ACCOUNT_LIFECYCLE_ACTION_HOLD
        and transition["transition_status"] == ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED
    ):
        protective_status = ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_HOLD_ELIGIBLE
    elif (
        action == ACCOUNT_LIFECYCLE_ACTION_HOLD
        and transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_HELD
    ):
        protective_status = ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_HELD
    elif (
        action == ACCOUNT_LIFECYCLE_ACTION_RELEASE
        and transition["transition_status"] == ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED
    ):
        protective_status = ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_RELEASE_ELIGIBLE
    elif (
        action == ACCOUNT_LIFECYCLE_ACTION_RELEASE
        and transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_NOT_ON_HOLD
    ):
        protective_status = ACCOUNT_LIFECYCLE_PRECONDITION_NOT_ON_HOLD

    return {
        **transition,
        "effective_state": effective_state,
        "protective_precondition_status": protective_status,
        "mapped_to_packet_vocabulary": (
            protective_status
            != ACCOUNT_LIFECYCLE_PROTECTIVE_PRECONDITION_INVALID
        ),
    }


def classify_promote_lifecycle_precondition(
    pool: str, manual_hold: bool
) -> dict[str, Any]:
    effective_state = classify_account_lifecycle_state(pool, manual_hold)
    transition = classify_account_lifecycle_transition(
        effective_state, ACCOUNT_LIFECYCLE_ACTION_PROMOTE
    )
    promote_status = ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_INVALID

    transition_precondition = str(transition["precondition_status"])

    if transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED:
        promote_status = ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED
    elif (
        transition_precondition
        == ACCOUNT_LIFECYCLE_PRECONDITION_HELD_RELEASE_REQUIRED
    ):
        promote_status = ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_BACKEND_ON_HOLD
    elif (
        transition["transition_status"] == ACCOUNT_LIFECYCLE_TRANSITION_CONDITIONAL
        and transition["target_state"] == ACCOUNT_LIFECYCLE_STATE_ACTIVE
        and bool(transition["requires_validation_sync_policy"])
    ):
        promote_status = ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_ELIGIBLE
    elif (
        transition_precondition
        == ACCOUNT_LIFECYCLE_PRECONDITION_NOT_LIFECYCLE_ACTION
    ):
        promote_status = ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_NOT_RESERVE

    return {
        **transition,
        "effective_state": effective_state,
        "promote_precondition_status": promote_status,
        "mapped_to_packet_vocabulary": (
            promote_status != ACCOUNT_LIFECYCLE_PROMOTE_PRECONDITION_INVALID
        ),
    }


def classify_demote_lifecycle_precondition(
    pool: str, manual_hold: bool
) -> dict[str, Any]:
    effective_state = classify_account_lifecycle_state(pool, manual_hold)
    transition = classify_account_lifecycle_transition(
        effective_state, ACCOUNT_LIFECYCLE_ACTION_DEMOTE
    )
    demote_status = ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_INVALID

    transition_precondition = str(transition["precondition_status"])

    if transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED:
        demote_status = ACCOUNT_LIFECYCLE_PRECONDITION_BACKEND_RETIRED
    elif transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RESERVE:
        demote_status = ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RESERVE
    elif (
        transition_precondition
        == ACCOUNT_LIFECYCLE_PRECONDITION_HELD_RELEASE_REQUIRED
    ):
        demote_status = ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_BACKEND_HELD
    elif (
        transition["transition_status"] == ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED
        and transition["target_state"] == ACCOUNT_LIFECYCLE_STATE_RESERVE
    ):
        demote_status = ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_ELIGIBLE
    elif (
        transition_precondition
        == ACCOUNT_LIFECYCLE_PRECONDITION_NOT_LIFECYCLE_ACTION
    ):
        demote_status = ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_NOT_ACTIVE

    return {
        **transition,
        "effective_state": effective_state,
        "demote_precondition_status": demote_status,
        "mapped_to_packet_vocabulary": (
            demote_status != ACCOUNT_LIFECYCLE_DEMOTE_PRECONDITION_INVALID
        ),
    }


def classify_retire_lifecycle_precondition(
    pool: str, manual_hold: bool
) -> dict[str, Any]:
    effective_state = classify_account_lifecycle_state(pool, manual_hold)
    transition = classify_account_lifecycle_transition(
        effective_state, ACCOUNT_LIFECYCLE_ACTION_RETIRE
    )
    retire_status = ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_INVALID

    transition_precondition = str(transition["precondition_status"])

    if transition_precondition == ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RETIRED:
        retire_status = ACCOUNT_LIFECYCLE_PRECONDITION_ALREADY_RETIRED
    elif (
        transition["transition_status"] == ACCOUNT_LIFECYCLE_TRANSITION_ALLOWED
        and transition["target_state"] == ACCOUNT_LIFECYCLE_STATE_RETIRED
    ):
        if pool == ACCOUNT_LIFECYCLE_POOL_ACTIVE:
            retire_status = ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_ELIGIBLE_ACTIVE
        elif pool == ACCOUNT_LIFECYCLE_POOL_RESERVE:
            retire_status = ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_ELIGIBLE_RESERVE
        else:
            retire_status = ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_NOT_RETIRABLE
    elif (
        transition_precondition
        == ACCOUNT_LIFECYCLE_PRECONDITION_NOT_LIFECYCLE_ACTION
    ):
        retire_status = ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_NOT_RETIRABLE

    return {
        **transition,
        "effective_state": effective_state,
        "retire_precondition_status": retire_status,
        "mapped_to_packet_vocabulary": (
            retire_status != ACCOUNT_LIFECYCLE_RETIRE_PRECONDITION_INVALID
        ),
    }


@dataclass(frozen=True)
class AccountLifecycleDependencies:
    list_accounts_impl: Callable[..., dict[str, Any]]
    run_protective_lifecycle_owner_path: Callable[..., dict[str, Any]]
    run_demote_impl: Callable[..., dict[str, Any]]
    run_onboard_impl: Callable[..., dict[str, Any]]
    run_promote_impl: Callable[..., dict[str, Any]]
    run_retire_impl: Callable[..., dict[str, Any]]


def list_accounts(
    paths: AccountLifecyclePaths,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.list_accounts_impl(paths)


def run_hold(
    paths: AccountLifecyclePaths,
    backend_id: str,
    reason: str | None,
    *,
    dry_run: bool = False,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_protective_lifecycle_owner_path(
        paths,
        backend_id,
        action="hold",
        reason=reason,
        dry_run=dry_run,
    )


def run_release(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_protective_lifecycle_owner_path(
        paths,
        backend_id,
        action="release",
    )


def run_demote(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_demote_impl(paths, backend_id)


def run_onboard(
    paths: AccountLifecyclePaths,
    *,
    auth_ref: str | None,
    loop: bool,
    skip_login: bool,
    no_sync: bool,
    non_interactive: bool,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_onboard_impl(
        paths,
        auth_ref=auth_ref,
        loop=loop,
        skip_login=skip_login,
        no_sync=no_sync,
        non_interactive=non_interactive,
    )


def run_promote(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    lock_acquired: bool = False,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_promote_impl(
        paths,
        backend_id,
        lock_acquired=lock_acquired,
    )


def run_retire(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_retire_impl(paths, backend_id)
