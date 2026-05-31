# WBP Native Quiescent Boundary Addendum

Date: 2026-05-25
Status: closed_success

## Goal

Freeze the exact truth boundary of the current quiescent contour so the stronger
dirty historical detached-executor fact cannot be implicitly inherited.

## Scope

In scope:

- accept the current quiescent contour packet truth exactly as emitted;
- explicitly reject inheritance of the historical launchd-detached executor
  semantics into the current contour;
- freeze exact non-claims for the current quiescent contour.

Out of scope:

- native filesystem proof;
- native window proof;
- native routing proof;
- source code edits;
- protected surface mutation.

## Accepted Truth Boundary

The current quiescent contour is accepted as:

```text
QUIESCENT_BASELINE_PROVEN_AND_PHASE7_ADMISSIBLE
```

because the current contour packet set directly proves:

- `fresh_context_verified=true`
- `phase7_retry_admissible=true`
- `hosted_by_protected_codex_session=false`
- `protected_codex_ancestry_disproven=true`
- `quiescent_current_codex_precondition_satisfied=true`

## Explicit Non-Inheritance Rule

The historical detached-executor packet under:

```text
audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/evidence/fresh_detached_context_host_chain_packet.json
```

contains a stronger fact:

```text
executor_ppid = 1
host_process_chain_length = 2
```

That historical launchd-detached executor fact is not inherited by the current
quiescent contour.

## Frozen Non-Claims

The current quiescent contour does not claim:

```text
launchd-detached executor capture for the current contour
native filesystem isolation proof
native window proof
native provider routing proof
Original Codex reversibility proof
runtime engine / CLIProxyAPI proof inside this contour
```

## Contour Capsule

resume from here: `closed_success`

verdict: ambiguity removed; current quiescent contour is accepted narrowly as
quiescent baseline proven and Phase 7 admissible, without inheriting the
historical launchd-detached executor semantics.
