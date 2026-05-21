<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Next Contour Canon Plan

PLAN_NAME: Next Contour Canon Plan
PLAN_VERSION: 1.8
PLAN_DATE: 2026-05-08
PLAN_OWNER: Product and Platform Team
PLAN_STATUS: Active; direct same-day 20-account re-entry closed `NO_GO` in `step37`; `step38` scope-freeze classification closed `NO_GO` on current runtime-truth blockers; `step39` read-only truth reproof closed `NO_GO` because bounded `sync --json` refresh is required but not yet owner-authorized in the active thread; `step40` is the current authorized single-sync runtime-truth reclear contour and is presently parked at its precondition gate until explicit owner authorization appears in the active thread; this document governs a bounded repair program composed of multiple small contours; once `step40` reopens and closes, the next lanes are reserve-first posture normalization, stage-20 re-entry, post-advance same-day validation, and canonical stop before design
PLAN_SCOPE: Repair proof posture and lifecycle truth through a bounded sequence of control-layer contours so the real working contour becomes canonically provable before basic companion UI work resumes

## Canon Priority

When sources conflict, decisions must follow this order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

This plan controls the next repair program and its small-contour sequence.
It does not override the governing product/runtime canon above.

## Trigger For This Plan

The previous direct re-entry attempt is closed `NO_GO`.

Observed facts from `step37`:

- `status --json` remained green:
  - `effective_mode=stable`
  - `policy_drift.status=clear`
  - `claim_gate.status=clear`
- `healthcheck --json` remained green:
  - `launch_readiness.status=ready`
  - `runtime_guardrails.status=clear`
- `rollout rotation inspect --json` remained green:
  - `selected_backend_snapshot_present=true`
  - `selected_backend_snapshot_validation_status=valid`
  - `participation_status=available`
- `accounts list --json` showed blocking posture:
  - `active_count=24`
  - `reserve_count=0`
  - `pool_policy.active_target=15`
- canonical owner surface
  `rollout stage advance 20 <id> --json`
  returned `STAGE_ADVANCE_BACKEND_NOT_ELIGIBLE`
  because the requested backend was not `reserve`

Supporting sources:

- `audit_results/step37_closeout_report.md`
- `audit_results/step37_decision_packet.json`
- `COMMAND_API.md`
- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`

## Purpose

Repair the gap between:

- real working runtime truth
- live registry lifecycle posture
- stage-20 canonical proof path

This contour exists to make the real contour canonically provable again.
It is not a rich UI contour, not an installer contour, and not a generic
runtime-expansion contour.

## Core Finding

The current blocker is not a broad runtime failure.
The current blocker is a mismatch between:

- the canonical reserve-first stage-20 owner path
- the live registry posture currently showing `24 active / 0 reserve`

The next contour must determine which of these is true:

- `LIVE_POSTURE_DRIFT_ONLY`
- `PROOF_MODEL_CONFLATES_MANAGED_POOL_WITH_ACTIVE_WINDOW`
- `INSUFFICIENT_ELIGIBLE_POOL`

No stage-20 proof or UI re-entry may proceed before that classification is
closed.

## Program Shape

This document is not one single write contour.
It is a bounded repair program that must be executed as a sequence of small
contours with closeout between them.

Default contour decomposition:

1. closed: `step38` scope freeze plus read-only classification
2. closed: `step39` read-only truth reproof plus authorization gate check
3. `step40` authorized single-sync runtime-truth reclear
   - current state: parked at precondition gate
   - reopen under the same contour id after explicit owner authorization
4. optional canon clarification contour
5. optional repo repair contour
6. live authorization plus normalization-decision contour
7. live normalization contour
8. post-normalization reclear contour
9. stage-20 owner-path proof contour
10. same-day scale validation contour
11. independent audit plus design-gate closeout contour

Contours may stop earlier on truthful `NO_GO`.
Contours must not be silently merged into one long write lane unless the
closeout explicitly justifies why the split could not be kept safely.

## Scope

In scope:

1. Worktree/scope split between execution-core, live evidence, and UI.
2. Read-only reality snapshot.
3. Root-cause classification for the `step37` blocker.
4. Optional docs/contract clarification for `managed pool` vs `active window`.
5. Optional repo repair if proof model is proven to read the wrong truth.
6. Repo verification, commit, and push boundary before any live mutation.
7. Live operation declaration and rollback expectation.
8. Live normalization decision packet.
9. Reserve-first live normalization through owner surfaces only.
10. Post-normalization reclear.
11. Canonical `rollout stage advance 20 <id> --json` proof attempt.
12. Same-day 20-account live validation only after successful stage-20
    advancement.
13. Evidence packet, independent audit, and design-gate stop token decision.

Out of scope:

1. Rich UI expansion.
2. Design polish.
3. Installer or packaging.
4. Engine-layer refactor without proven blocker.
5. Hidden best-reserve logic.
6. Manual edits to `backend-registry.json`.
7. Recasting the product as `active-only` without a separate architecture
   decision contour.

## Layer Boundary

Control-layer only in this contour:

- lifecycle policy
- profile orchestration
- runtime truth
- fallback and recovery
- command API truth
- stage progression proof posture
- evidence capture and audit

Forbidden in this contour:

- patching `CLIProxyAPI` without a proven blocker
- using logs as the primary API when canonical JSON surfaces exist
- converting live validation into engine refactor
- using UI work to mask unresolved execution-core blockers

## Branch Decision After Classification

After read-only classification, exactly one branch becomes active.

### Branch A: `LIVE_POSTURE_DRIFT_ONLY`

Use this when:

- command contract is correct
- tests support current semantics
- runtime surfaces are green
- live registry posture is the primary mismatch

Action:

- skip repo repair
- proceed to live authorization, normalization decision, and reserve-first
  normalization

### Branch B: `PROOF_MODEL_CONFLATES_MANAGED_POOL_WITH_ACTIVE_WINDOW`

Use this only when:

- code, tests, and contract show that the proof path reads the wrong truth
- the issue is repo-owned, not only live-state-owned

Action:

- open a bounded repo repair contour
- add tests first or in the same bounded change set
- verify, commit, and push before any live mutation starts

### Branch C: `INSUFFICIENT_ELIGIBLE_POOL`

Use this when:

- there is no explicit eligible reserve candidate
- or the live pool does not have enough healthy/valid accounts for safe
  stage-20 progression

Action:

- stop
- do not run `rollout stage advance 20 <id> --json`
- do not hide the stop behind UI work
- reopen only the blocking pool/readiness contour

## Canon Clarification Rule

If clarification is needed, it must preserve reserve-first canon rather than
rewrite the system into `active-only`.

The accepted clarification is:

- `managed_pool_count`: total managed inventory known to the control layer
- `active_window`: accounts currently allowed to participate in active routing
  under the staged policy
- `reserve_depth`: managed accounts available for explicit promotion and staged
  expansion
- `launch_capable`: accounts currently healthy enough to launch or route

Important truth:

- `25 managed accounts` does not mean `25 active-routing accounts`
- `24 active / 0 reserve` is not an acceptable substitute for reserve-first
  stage-20 proof

If clarification contradicts `COMMAND_API.md` or the stage-advance tests,
resolve the repo contract first and do not enter live normalization until the
contract is verified.

## Repo Repair Boundary

Repo repair is conditional, not automatic.

If Branch B is selected:

1. limit repo changes to proof/truth/contract scope only
2. add or update tests that prove the specific bug
3. verify targeted tests and relevant broader tests
4. review diff for scope discipline
5. commit and push
6. only then reopen the live lane

Live normalization must never begin against an unverified local-only repair.

## Target Posture Before Stage-20 Proof

Before attempting `rollout stage advance 20 <id> --json`, the contour must
reach this posture:

1. current stage remains canonical `15` or explicit in-progress stage truth is
   acceptable under `COMMAND_API.md`
2. `status --json` remains green enough to avoid false-green or stale-green
   claims
3. `healthcheck --json` remains green enough to keep launch/fallback truth
   honest
4. `rollout rotation inspect --json` remains valid
5. active window is intentionally bounded to the stage-15 target posture
6. reserve depth is restored
7. one explicit eligible reserve backend id is identified for stage-20
   advancement
8. protected active backends are preserved
9. no undocumented live mutation remains in flight

The target posture is not "make counts look pretty".
The target posture is "make staged progression truthful and provable".

## Live Start Gate

Live lane may start only when all conditions are true:

1. root-cause classification is closed
2. if repo repair occurred, it is verified, committed, and pushed
3. owner authorization for live-runtime action is explicit in the current
   thread
4. live operation declaration is recorded before execution
5. mandatory read-only snapshot is captured in strict JSON form

## Live Operation Declaration

Before any real-path mutation, declare:

1. exact commands to be executed
2. exact real paths that may be read
3. exact real paths that may be written
4. rollback or backup expectation

No live command may be treated as harmless merely because it emits JSON.

## Mandatory Read-Only Snapshot

Capture, without mutation:

1. `status --json`
2. `healthcheck --json`
3. `accounts list --json`
4. `rollout rotation inspect --json`

The snapshot must record:

- desired and effective mode
- `claim_gate`
- `policy_drift`
- pool counts
- healthy/degraded/down summary
- launch-capable backend ids or equivalent truthful summary
- selected backend evidence
- rotation participation evidence

If runtime truth is not green enough at this step, repair runtime truth first.
Do not proceed into rollout posture work on top of a broken truth layer.

`launch smoke --json` is intentionally excluded from this read-only snapshot.
It remains a bounded live activation seam, not a pure observation surface.
Use it only in an explicitly authorized live contour such as post-normalization
reclear or a later live preflight where activation evidence is required by the
approved lane.

## Normalization Decision Packet

Before live mutation, build a decision packet that names:

1. `protected_active`
2. `reserve_candidate`
3. `reserve_set`
4. `hold_set`
5. `retire_set`
6. `do_not_touch`
7. expected target posture after normalization

Rules:

- do not demote or retire healthy working backends mechanically just to satisfy
  a pretty count
- do not silently sacrifice fallback or recovery depth
- do not proceed if no explicit reserve candidate can be named

## Live Normalization Rule

Live normalization must use owner surfaces only.

Allowed mutation surfaces include:

- `accounts ... --json`
- `policy stage set ... --json`
- `sync --json`

Forbidden mutation methods:

- direct edit of `backend-registry.json`
- hidden one-off scripts that bypass owner surfaces
- staged-pool mutation through UI-only paths

The result must preserve the working active window while restoring truthful
reserve-first posture.

## Post-Normalization Reclear

After normalization, rerun:

1. `sync --json`
2. `rollout rotation inspect --json`
3. `status --json`
4. `healthcheck --json`
5. `launch smoke --json`
6. `accounts list --json`

Required outcomes:

- `claim_gate.status=clear`
- `policy_drift.status=clear`
- rotation evidence remains valid
- runtime guardrails remain clear
- stable fallback remains available
- target posture is actually observed, not assumed

If this reclear fails, stop before stage-20 proof.

## Stage-20 Owner-Path Proof

Only after successful reclear may the contour run:

```sh
python3 -m wild_boar_proxy rollout stage advance 20 <reserve-id> --json
```

Success must prove, machine-readably:

- explicit backend id input
- explicit reserve eligibility
- one-step controlled advancement
- postflight attestation status
- postflight rotation status
- rollback readiness status

If this command fails again:

- record the new blocker honestly
- do not proceed into same-day high-load validation
- do not proceed into UI

## Same-Day 20-Account Validation Re-entry

Same-day 20-account live validation is allowed only if stage-20 owner-path
proof succeeds first.

This follow-up validation contour must:

1. keep control-layer scope only
2. exercise the real environment under operator-approved high load
3. collect runtime attestation under load
4. collect rotation participation evidence under load
5. collect truthful pool counts under load
6. verify fallback readiness and deterministic recovery readiness
7. avoid any engine-layer refactor or hidden contract expansion during the run

The scale claim remains evidence-driven.
Successful stage advancement alone is not the full scale proof.

## Explicit `NO_GO` Table

Use these blocker codes or their direct equivalents when closing the contour:

- `RUNTIME_TRUTH_NOT_GREEN`
- `LIVE_POSTURE_DRIFT_UNCLASSIFIED`
- `PROOF_MODEL_REPAIR_UNVERIFIED`
- `REPO_REPAIR_NOT_PUSHED`
- `LIVE_RUNTIME_OWNER_AUTH_NOT_EXPLICIT`
- `LIVE_OPERATION_DECLARATION_MISSING`
- `STRICT_JSON_CONTRACT_BROKEN`
- `RESERVE_CANDIDATE_NOT_IDENTIFIED`
- `INSUFFICIENT_ELIGIBLE_POOL`
- `TARGET_POSTURE_NOT_REACHED`
- `POST_NORMALIZATION_RECLEAR_FAILED`
- `STAGE20_OWNER_PATH_UNAVAILABLE`
- `SAME_DAY_SCALE_VALIDATION_FAILED`
- `ENGINE_BLOCKER_ESCALATION_REQUIRED`

No blocker may be reworded into generic optimism.

## Artifacts Required

This contour must produce:

1. read-only snapshot packet
2. root-cause classification note
3. optional contract clarification note
4. optional repo repair closeout with commit hash and push status
5. live operation declaration
6. normalization decision packet
7. post-normalization verification packet
8. stage-20 proof packet
9. same-day validation evidence packet if stage-20 proof succeeded
10. independent audit closeout

Artifacts must remain redacted and must not include secrets, auth files,
private runtime dumps, or unredacted logs.

## Canonical Stop Before Design

The contour may transition toward UI only after this stop token is truthfully
earned:

`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`

This token may be set only if all conditions are true:

1. runtime truth is green:
   - `status --json`
   - `healthcheck --json`
   - `launch smoke --json` when required by the contour
   - `rollout rotation inspect --json`
2. reserve-first lifecycle posture is canonical or explicitly clarified without
   contradicting command truth
3. stage-20 owner-path is either:
   - passed and followed by successful same-day validation, or
   - closed with a non-repo-owned `NO_GO` that does not leave execution-core
     truth ambiguous
4. no repo-owned execution-core blocker remains open
5. no live-runtime mutation remains undocumented
6. UI/design changes are not mixed into execution-core closeout
7. branch state is committed and pushed
8. final closeout names verification commands, commit hash, branch, and next
   contour

Until this token is earned:

- no rich UI expansion
- no design polish contour
- no masking execution-core blockers behind UI progress

If the stop token is earned through the second path above
(`non-repo-owned NO_GO` with clear execution-core truth), only `basic companion
UI` may reopen.
That reopening:

- must not claim scale closure
- must not imply `scale-to-20 validated`
- must not hide the unresolved scale blocker
- must keep the scale contour open as a separate later contour

## Success Criteria

This plan succeeds when:

1. the `step37` blocker is honestly classified
2. the necessary branch is executed without mixing repo and live lanes
3. reserve-first stage-20 owner-path becomes available and truthful again
4. same-day 20-account validation is either completed with evidence or closed
   by an explicit truthful `NO_GO`
5. the repo reaches a canonical stop before design

## Final Discipline

This repair contour is intentionally narrower than a general product plan.

Choose:

- truth over optimism
- reserve-first lifecycle truth over active-only drift
- explicit owner surfaces over hidden mutation
- repo/live separation over convenience
- design gate discipline over premature UI expansion
