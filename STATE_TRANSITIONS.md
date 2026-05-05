<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# State Transitions

## Purpose

This document freezes the allowed account-state transitions for Execution
Wave 1A.

`backend-registry.json` remains the serialized source of truth for lifecycle
state.

## State model

- `reserve`: backend is present but not on active routing
- `active`: backend is eligible for active routing
- `hold`: operator-visible quarantine state serialized as `manual_hold=true`
- `retired`: backend is removed from service with no automatic return path

`hold` is not a separate lifecycle token in the registry schema.
It is a routing-blocking state derived from `manual_hold=true`.

## Allowed transitions

- `new auth -> reserve`
- `reserve -> active` only after validate plus sync plus operator or policy
  decision
- `active -> hold` when the backend degrades, becomes suspicious, or is placed
  on manual hold
- `hold -> reserve` only after explicit release
- `active -> retired` when the backend is intentionally removed from service
- `reserve -> retired` when the backend is rejected or deprecated

## Disallowed transitions

- `new auth -> active`
- `hold -> active` directly
- `retired -> reserve`
- `retired -> active`
- any automatic return from `retired`

## Routing rule

Any backend in `hold` or `retired` is excluded from active routing.

Any transition that would change active routing must preserve a rollback point
before switch.

## Rollback expectation

Transitions that affect active routing must follow one serialized transaction:

1. snapshot current registry and related runtime state
2. stage the proposed transition
3. verify resulting routing inputs
4. switch atomically
5. rollback on verification failure or unsafe write failure

No routing-impacting transition is complete if rollback data is missing.

## Transition notes

- reserve-first onboarding is mandatory
- manual hold is protective, not promotional
- release from hold returns to `reserve`, not directly to `active`
- retirement is terminal for automatic policy logic
