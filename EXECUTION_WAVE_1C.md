<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Execution Wave 1C

## Position

Execution Wave 1C is the execution-core closeout and live-evidence separation
contour.

It follows:

- Wave 1A `Execution Core Spec Freeze`
- Wave 1B runtime-hardening implementation

It does not open UI, installer, packaging, or legacy-import work.

## Purpose

- close narrow remaining execution-core confidence gaps without inventing new
  truth surfaces
- keep the 16-account live evidence capture as a separate operational lane
  controlled by `EVIDENCE_CAPTURE_RUNBOOK.md`
- prepare a clean handoff either to a basic companion UI contour or to a new
  narrowly justified runtime-hardening contour

## Starting Assumptions

This contour assumes the starting branch already contains:

- repo-owned Wave 1 command surfaces
- a passing local CLI suite before new repo-write work begins
- diagnostics export redaction hardening
- a 16-account contour that remains observed field evidence until a
  machine-carried packet is captured through the owner surface

This baseline does not imply:

- `STABLE_20_PROVED`
- `SCALE_COMPLETE`
- `PILOT_READY`
- `production_ready`

## Non-Negotiable Boundaries

- one active truth surface per topic
- no split-brain between docs and runtime
- no false-green or stale-green status
- no runtime data committed
- no UI, installer, packaging, or legacy-import work in this contour
- no engine-layer duplication
- no live-runtime mutation without explicit operator approval

## Contour Split

Wave 1C has two lanes.

They must not be mixed into one closeout:

1. repo-write lane
2. live evidence lane

Repo-write lane may close without live evidence lane.

Live evidence lane does not authorize additional repo-write work by itself.

## Repo-Write Lane

### In scope

- narrow execution-core hardening that is already implied by existing
  contracts
- direct test coverage for already-owned command surfaces when coverage is
  materially weaker than the contract
- doc clarifications that remove ambiguity between `CANON.md`,
  `MASTER_PLAN.md`, `COMMAND_API.md`, and runtime behavior
- security hardening only when it closes a direct control-layer leak or truth
  bug

### Preferred candidates

- `rollout stage advance` lock coverage
- detected-new-auth onboarding lane expansion

### Recently closed contour

Recently closed:

`Wave 1C Repo-Write: Accounts Onboard Explicit Skip-Login Owner-Surface Coverage`

Closeout:

- direct owner-surface coverage was added for:
  - `accounts onboard --json --auth-ref <path> --skip-login`
- the contour now proves:
  - the explicit `--skip-login` lane has direct machine-verified coverage
  - successful packets still carry reserve-first onboarding truth honestly
  - mismatch paths do not emit false success claims
- the contour closed as tests-only

### Current next contour

The immediate next repo-write contour is:

`Wave 1C Repo-Write: Rollout Stage Advance Lock Coverage`

Purpose:

- close the remaining direct lock-coverage gap on the stage-advance owner
  surfaces
- prove fail-closed owner-surface behavior under held-lock conditions on
  representative stage-advance branches
- strengthen `STATE_SERIALIZATION_GATE` confidence on a delegated multi-step
  mutating owner surface without claiming stage-proof completion, scale proof,
  or broader rollout completion

Scope:

- tests first
- direct coverage for:
  - `rollout stage advance 15 <id> --json` from canonical source stage `10`
  - `rollout stage advance 20 <id> --json` from canonical requested stage `20`
    when target posture is not yet satisfied
- prove observable owner-surface failure expectations only:
  - `machine_error_code == LOCK_HELD`
  - `changed_files == []`
  - tracked state remains unchanged
  - no committed control-layer mutation is observed in canonical write surfaces
- do not assert absence of read-only delegated preflight or proof work unless
  that fact is already surfaced machine-readably
- allow a minimal runtime fix only if a new test reveals a real missing
  serialized-path guard or fail-open behavior in the stage-advance owner
  surface

Acceptance:

- direct lock-held coverage exists for two distinct stage-advance owner-flow
  branches
- held-lock results emit non-success owner packets with `LOCK_HELD`
- no committed control-layer mutation is observed under held-lock conditions
- no new truth surface is introduced
- full local CLI suite remains green
- the contour closes as tests-only unless a failing test proves a real defect

Decision rule:

- if tests pass once added, close the contour as tests-only
- if a new test reveals a real defect, fix only the control-layer
  stage-advance lock-preflight or serialized-path defect in the same contour
- if a fix would expand into stage-proof semantics, rollout-policy redesign,
  engine-layer work, or live operational behavior, stop and open a separate
  contour

Explicitly deferred from this contour:

- detected-new-auth onboarding lane expansion
- exhaustive lock coverage across every remaining mutating command
- stage-advance semantic expansion beyond held-lock behavior
- live `rollout evidence capture 16 --json`
- scale-to-20 proof claims

### Out of scope

- new command surfaces
- new state files
- live auth, proxy, profile, or host-client mutation
- scale-to-20 proof work
- UI-oriented shaping that invents a new truth surface
- installer, reset, uninstall, packaging, codesign, notarization

## Live Evidence Lane

Live evidence is controlled only by `EVIDENCE_CAPTURE_RUNBOOK.md`.

This lane is operational, not repo-authoring.

### Required owner marker

The current thread must contain an explicit operator marker before execution:

```text
GO_FOR_LIVE_CAPTURE: run rollout evidence capture 16 --json once
```

### Allowed command

Exactly one live command is allowed per approved run:

```sh
rollout evidence capture 16 --json
```

### Required validations

- `stdout` is exactly one JSON object
- `scale_evidence_packet_result` is present
- `claim_scope == field_evidence_observed_only`
- `packet_status` is one of:
  - `complete`
  - `incomplete`
  - `contradicted`
  - `unsafe_to_claim`
- runtime attestation summary is present
- rotation evidence summary is present
- fallback readiness summary is present
- diagnostics bundle is redacted
- no forbidden write-surface mutation occurred

### Forbidden outcomes

The lane must not produce or imply:

- `stable_16_proved`
- `stable_20_proved`
- `scale_complete`
- `pilot_ready`
- `production_ready`

The lane must not commit or stage:

- evidence bundles
- auth files
- raw runtime dumps
- raw logs
- private tokens
- proxy credentials

## Entry Criteria

Wave 1C starts only when:

- the worktree is clean or the contour is explicitly a hygiene contour
- no previous write contour is left local-only
- no unresolved contradiction with `CANON.md` exists
- the exact target gap is concrete and bounded
- no live GO marker is inferred from a generic phrase such as `start` or `go`

Additional repo-write entry criteria:

- the target change is repo-authored
- the target change can be verified without touching live runtime paths

Additional live-lane entry criteria:

- the explicit owner GO marker exists in the current thread
- the real paths that may be read or written are declared before execution
- rollback expectations are declared before execution

## Acceptance Criteria

### Repo-write lane

- changes stay within control-layer ownership
- each changed behavior has tests or a documented verification command
- no runtime artifacts are staged or committed
- the branch is pushed in the same closeout cycle as verification and commit
- the contour is merged without tail branches or dirty leftovers

### Live evidence lane

- packet claim stays at `field_evidence_observed_only`
- no forbidden mutation occurs
- bundle redaction passes
- factual report names packet status and blocked reasons honestly
- runtime artifacts stay out of git history

## Handoff Rule

Wave 1C closes only when one of these is true:

1. remaining repo-authored execution-core deltas are closed or explicitly
   deferred with rationale, and the next contour can move to a basic companion
   UI contour
2. live evidence or new tests expose a real blocker, and the next contour is a
   separate narrowly scoped runtime-hardening contour

Live evidence pending operator approval is an allowed open item.
It does not block repo-write closeout by itself.
