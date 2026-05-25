# WBP Native Window Proof Runner Surface Preparation

Date: 2026-05-25
Status: closed_success

## Goal

Freeze whether Phase 9 native window proof is executable as a bounded audited
contour right now, and if not, freeze the exact missing runner-surface and
observation-contract blockers.

## Scope

In scope:

- inspect current native launch dispatch and contract code;
- inspect historical live native window evidence;
- determine whether a canonically admitted runnable Phase 9 runner surface
  already exists;
- freeze the observation contract and expected blocked reasons.

Out of scope:

- live native window proof attempt;
- launcher or observation code repair;
- filesystem proof rerun;
- provider routing proof;
- prompt/response proof.

## Binary Verdict

```text
PHASE9_WINDOW_PROOF_BLOCKED_PENDING_RUNNER_PREPARATION
```

## Why

- packet builders and contract validators exist, but they are not the same thing
  as a canonically admitted runnable live runner surface;
- the only canonically reusable runner surface in current code truth is the
  CLI runner, which is explicitly non-native;
- historical native window contours prove prior behavior and prior blockers, but
  do not freeze a reusable Phase 9 runner command surface;
- historical live attempts remain blocked on window binding and current-Codex
  protection.

## Frozen Observation Contract

The native window proof contract already expects a later live runner to provide:

```text
native_dispatch_authorization
native_custom_launch
process_lineage
window_observation
window_identity_binding
native_window_ui_surface
current_codex_running_state_before
current_codex_running_state_after
cleanup_reversibility
native_window_proof_summary
independent_native_window_audit
```

The authoritative observation mechanism currently evidenced in prior live work is:

```text
AX/System Events process by unix id over launch process group
```

## Frozen Expected Blocked Reasons

```text
pid_visible_but_accessible_window_absent
SystemEventsInvalidIndex
window identity not bound to launch pid/process group
CURRENT_CODEX_PROTECTION_NOT_PROVEN
```

## Contour Capsule

resume from here: `closed_success`

verdict: Phase 9 cannot start honestly yet because the repo still lacks a
canonically admitted reusable native window-proof runner surface, even though
packet/contract builders and historical live evidence already exist.
