# RUNTIME_TAIL_SPLIT_DECISION_GATE Closeout

Date: 2026-05-13

Head before artifacts: `08969cb`

Final state: `RUNTIME_TAIL_SPLIT_DECISION_READY_OWNER_APPROVAL_REQUIRED`

## Scope

This was a decision-only contour for the remaining dirty `runtime.py` tail.

Allowed writes:
- `audit_results/runtime_tail_split_decision_matrix_2026-05-13.json`
- `audit_results/runtime_tail_split_decision_closeout_2026-05-13.md`

Not allowed in this contour:
- runtime edits
- runtime revert
- UI edits
- test edits
- live runtime commands
- accepting the dirty runtime behavior as canon

## Observed Runtime Tail

The dirty runtime diff remains one file:

- `wild_boar_proxy/runtime.py`
- 16 insertions
- 1 deletion
- 3 textual diff hunks
- 2 behavior buckets

Bucket 1:

- ID: `RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_DECISION`
- Function: `dispatch_external_client`
- Surfaces: `launch client --json`, `launch smoke --json`
- Meaning: add a bounded settle loop after detached process spawn.
- Risk: timing wait must not become hidden runtime health truth or silently broaden launch success.
- Revertability: likely independently revertible.

Bucket 2:

- ID: `RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_DECISION`
- Function: `run_promote`
- Surfaces: `accounts promote <id> --json`, `rollout stage advance ... --json`
- Meaning: allow the lock-acquired stage-advance owner path to rely on later postflight proof for selected-backend participation.
- Risk: direct promote must remain stricter than the stage-advance owner path, and stage advance must fail closed if postflight proof is missing.
- Revertability: likely independently revertible.

## Decision

The remaining `runtime.py` tail should not be treated as one mixed owner decision.

It should be split into two later runtime gates:

- `RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_DECISION`
- `RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_DECISION`

Both require explicit owner approval before accept, revert, or deeper implementation work.

## Independent Inspection

A read-only inspector checked the dirty runtime diff and reported:

- the launch dispatch hunk is independent from the promote/stage-advance hunk
- the promote/stage-advance hunk is independent from the launch dispatch hunk
- the launch bucket may affect both launch client and launch smoke surfaces
- the promote bucket affects direct promote and rollout stage-advance owner paths
- a later stop condition should trigger if a third runtime hunk appears or if either hunk starts affecting unrelated command surfaces

## Missing Later Verification

Launch dispatch bucket:

- prove the settle window is needed without relying on post-return polling
- prove the wait is bounded and cannot hang the command surface
- prove return packet shape and command meaning are unchanged
- prove launch smoke and launch client do not claim runtime health from timing behavior

Promote/stage-advance bucket:

- prove direct non-lock promote still requires selected-backend verification
- prove lock-acquired stage-advance delegates selected-backend proof to postflight verification
- prove missing postflight selected-backend proof fails closed
- prove rollback behavior remains intact when active placement or policy proof fails

## Scope Check

No runtime code was edited in this contour.

No UI code was edited in this contour.

No tests were edited in this contour.

No live runtime command was executed in this contour.

The dirty generated evidence tail remains separate from this decision.

## Verification

Local verification:

- `python3 -m json.tool audit_results/runtime_tail_split_decision_matrix_2026-05-13.json`
- service-trace scan over the two new artifacts
- token/local-path scan over the two new artifacts
- `git diff --check -- wild_boar_proxy/runtime.py audit_results/runtime_tail_split_decision_matrix_2026-05-13.json audit_results/runtime_tail_split_decision_closeout_2026-05-13.md`

Independent artifact audit:

- PASS for decision-only framing
- PASS for two-bucket split
- PASS for owner-approval requirement
- PASS for no UI/code/test scope creep in the artifacts
- PASS for no obvious service traces or absolute local paths in the artifacts

Audit caveat:

- the artifact audit was used only for artifact consistency
- local git commands remain the source for the current dirty `runtime.py` status

## Owner Decision Required

The owner must choose one of:

- review and test the launch-dispatch bucket first
- review and test the promote/stage-advance bucket first
- approve reverting one or both runtime buckets
- keep both pending and pause UI freeze work

Until that happens, the UI freeze path should treat the runtime tail as unresolved.
