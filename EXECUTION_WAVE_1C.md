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

- `rollout stage advance` serialized owner-path closure plus interleaving audit
- detected-new-auth onboarding lane expansion

### Recently closed contours

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

Recently closed:

`Wave 1C Repo-Write: Rollout Stage Advance Serialized Owner-Path Closure`

Closeout:

- composite stage advancement now executes through one serialized owner path
  across:
  - proof
  - policy transition
  - promotion
  - stable inventory materialization
  - postflight verification
- nested owner helpers in the same thread no longer create a false self-lock
  outcome while the composite owner path is held
- the contour now proves:
  - held-lock results emit non-success owner packets with `LOCK_HELD`
  - cross-thread competing owner mutation is rejected while stage advance is in
    flight
  - `changed_files` remains empty under rejected competing mutation
  - tracked state remains unchanged under rejected competing mutation
  - no interleaving window remains between proof, policy mutation, promotion,
    stable inventory materialization, and postflight verification
- direct owner-surface verification now covers:
  - `rollout stage advance 15 <id> --json` from canonical source stage `10`
  - `rollout stage advance 20 <id> --json` from canonical requested stage `20`
    when target posture is not yet satisfied
  - cross-thread competing `mode set stable --json` rejection during in-flight
    stage advancement
- the contour closed with runtime hardening plus direct tests

Recently closed:

`Wave 1C Repo-Write: Detected-New-Auth Onboarding Owner-Surface Coverage`

Closeout:

- direct owner-surface coverage was added for detected-new-auth onboarding:
  - external onboard command non-zero exit with unique reserve backend and full
    post-proof success
  - `--no-sync` detected-new-auth path without sync overclaim
  - status-proof failure without false `reserve_only_success`
- the contour now proves:
  - successful detected-new-auth packets do not infer final truth from external
    command exit code alone
  - skipped sync remains machine-visible as skipped
  - status-proof failure stops success claims honestly
- the contour closed as tests-only

### Repo-Write Lane Closeout Status

The Wave 1C repo-write lane preferred candidates are closed.

No known repo-authored execution-core delta remains in the preferred candidate
set.

`STATE_SERIALIZATION_GATE` no longer has a known repo-authored reopen window in
the stage-advance owner path.

This is not a claim that all of Wave 1C is fully complete. The live evidence
lane executed once and closed as `incomplete`.

The freshness blocker was closed through a truthful operational prerequisite
refresh.
No repo-owned defect has been identified in the current control-layer
freshness logic path.

The separate live rerun contour also executed and closed as `incomplete`.
The factual blocker packet carried:

- `runtime_attestation_summary.machine_error_code == LISTENER_DOWN`
- `rotation_evidence_summary.machine_error_code == ROTATION_EVIDENCE_STALE`
- `fallback_readiness_summary.machine_error_code == STAGE_PROOF_ROLLBACK_READINESS_FAILED`
- `fallback_readiness_summary.reason == consumer_activation_readiness_not_ok`

The managed-runtime activation blocker investigation then observed:

- current `healthcheck --json` passed after owner-path reconciliation and
  reported final live truth in `stable`
- current `status --json` passed and reported
  `consumer_activation_readiness.status == aligned`
- current `rollout rotation inspect --json` remained
  `ROTATION_EVIDENCE_STALE` with
  `evidence_reason == selected_backend_snapshot_stale`

No repo-owned defect has been proven in the current activation or fallback
classification paths.
The rotation freshness operational prerequisite contour then observed:

- exactly one `sync --json` completed successfully
- current `rollout rotation inspect --json` returned `machine_error_code == OK`
- current rotation evidence now reports `evidence_freshness == fresh`
- current rotation evidence now reports `participation_status == available`

The rotation freshness blocker was closed through truthful owner-path refresh.
The next contour then became a separate live evidence rerun contour.

That rerun also closed as `incomplete`.
The factual packet carried:

- `runtime_attestation_summary.machine_error_code == LISTENER_DOWN`
- `rotation_evidence_summary.machine_error_code == ROTATION_EVIDENCE_STALE`
- `rotation_evidence_summary.evidence_reason == selected_backend_snapshot_stale`
- `fallback_readiness_summary.machine_error_code == STAGE_PROOF_ROLLBACK_READINESS_FAILED`
- `fallback_readiness_summary.reason == consumer_activation_readiness_not_ok`

The evidence-capture regression blocker investigation then observed:

- the packet builder aggregates separate attestation, rotation, and fallback
  axes rather than encoding a single causal hierarchy
- current docs and code do not prove one of the three rerun blockers is the
  root cause of the other two
- no repo-owned defect has yet been proven in the current activation or
  fallback classification paths

The multi-axis live readiness operational prerequisite contour then observed:

- current `healthcheck --json` returned `machine_error_code == OK`
- current `healthcheck --json` reported attestation pass on
  `effective_mode == stable`
- current `status --json` returned
  `consumer_activation_readiness.machine_error_code == OK`
- current `status --json` returned
  `consumer_activation_readiness.status == aligned`
- current `rollout rotation inspect --json` remained
  `ROTATION_EVIDENCE_STALE` with
  `evidence_reason == selected_backend_snapshot_stale`
- exactly one `sync --json` completed successfully
- immediate parallel post-sync validation produced `LOCK_HELD` on
  `healthcheck --json` and `status --json` while
  `rollout rotation inspect --json` already reported fresh participation
  evidence
- that `LOCK_HELD` episode was treated as operator-induced contention rather
  than a contour blocker because the later sequential revalidation succeeded
- sequential revalidation then returned:
  - `healthcheck --json` `machine_error_code == OK`
  - current attestation `listener_ok == true`
  - current attestation `models_ok == true`
  - current attestation `responses_ok == true`
  - current attestation `effective_mode_match == true`
  - current attestation `base_url_match == true`
  - `status --json`
    `consumer_activation_readiness.machine_error_code == OK`
  - `status --json`
    `consumer_activation_readiness.status == aligned`
  - `rollout rotation inspect --json` `machine_error_code == OK`
  - current rotation evidence `evidence_freshness == fresh`
  - current rotation evidence `participation_status == available`

The live-readiness prerequisite contour was closed through truthful owner-path
refresh and sequential revalidation.
The next contour is now a separate live evidence rerun contour.

The live evidence rerun contour then observed:

- exactly one approved `rollout evidence capture 16 --json`
- top-level `status == ok`
- top-level `machine_error_code == OK`
- `claim_target == "16"`
- `claim_scope == field_evidence_observed_only`
- `packet_status == complete`
- `final_outcome == field_evidence_packet_complete`
- `runtime_attestation_status == passed`
- `strict_json_command_api_status == passed`
- `state_serialization_status == passed`
- `rotation_evidence_status == available`
- `fallback_readiness_status == ready`
- `diagnostics_redaction_status == passed`
- `blocked_reasons == []`
- `scale_gate_summary.gates.SCALE_EVIDENCE_PACKET_GATE.status == passed`
- `scale_gate_summary.all_gates_passed == true`

The live evidence lane was closed as `field_evidence_observed_only`.
No stronger scale claim was produced.

### Next Handoff Recommendation

No additional Wave 1C live evidence rerun contour is currently open after this
complete closeout.

Any follow-on contour must be chosen separately under `MASTER_PLAN.md` and
`CANON.md`.

`Wave 1D Basic Companion UI Readiness` may open only as a separate
fallback/readiness-spec branch after the scale lane is explicitly deferred.

### Canonical Closeout Boundary

This closeout proves only:

- `field_evidence_observed_only`
- `field_evidence_packet_complete`
- `SCALE_EVIDENCE_PACKET_GATE` passed for this rerun packet

This closeout does not prove or imply:

- `stable_16_proved`
- `stable_20_proved`
- `scale_complete`
- `pilot_ready`
- `production_ready`

The first UI contour must:

- consume existing strict JSON command surfaces as the truth source
- preserve desired mode, effective mode, endpoint, health, and pool state as
  read from existing command packets
- avoid inventing a new truth surface
- avoid UI polish, installer, packaging, legacy import, or scale proof work
- stop and open a separate runtime-hardening contour if new evidence or tests
  expose a real execution-core blocker

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

### Required owner authorization

The current thread must contain owner authorization before execution.
This may be either the standing owner approval recognized by `CANON.md` or the
exact one-off operator marker:

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
- `changed_files` list bundle artifact file paths only, not live runtime files
- no forbidden write-surface mutation occurred

### Required post-run checks

After the live command and before any closeout statement:

```sh
git status --short --branch
git diff --name-only --cached
```

No redacted evidence bundle, temp export artifact, auth file, runtime state,
log, or private config path may be staged.

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
- no live authorization is inferred from a generic phrase such as `start` or
  `go` unless the thread already contains standing owner approval recognized by
  `CANON.md`

Additional repo-write entry criteria:

- the target change is repo-authored
- the target change can be verified without touching live runtime paths

Additional live-lane entry criteria:

- owner authorization exists in the current thread
- if the live lane follows repo-write work in the same thread, that repo-write
  contour is already committed and pushed before live execution begins
- the real paths that may be read are declared before execution
- the exact redacted evidence bundle or temp export artifact paths that may be
  written are declared before execution
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
- only redacted evidence bundle or temp export artifact paths are written
- artifact copies of runtime mode files are allowed only inside the redacted
  export directory, never on live runtime paths
- runtime artifacts stay out of git history

## Handoff Rule

Wave 1C repo-write handoff is allowed when one of these is true:

1. remaining repo-authored execution-core deltas are closed or explicitly
   deferred with rationale, and the next contour can move to a basic companion
   UI contour
2. live evidence or new tests expose a real blocker, and the next contour is a
   separate narrowly scoped runtime-hardening contour

The repo-write lane currently satisfies condition 1.

Live evidence pending operator approval is an allowed open item.
It does not block repo-write closeout by itself.
