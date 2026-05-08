CONTOUR:
Goal:
Realign control-owned stable inventory and obtain approved-target activation
evidence so owner surfaces can stop delegating policy drift to the dirty
observed auth-dir. Then re-measure whether runtime truth is green enough to
open live posture normalization.

Size: M
Risk level: high
Decision owner: operator + maintainer
Mode: live-proof

Execution identity:
- this is `step41`
- `step40` closed `NO_GO_RUNTIME_RECLEAR_FAILED`
- `step41` is a bounded control-layer truth-realignment contour, not a posture
  normalization contour

Canon order:
1. CANON.md
2. MASTER_PLAN.md
3. RUNTIME_CONTRACT.md
4. STATE_SCHEMA.md
5. COMMAND_API.md
6. DELIVERY_RULES.md
7. README.md

Precondition:
- explicit owner authorization is already present in the active thread

In scope:
- `stable target switch --apply --json`
- `stable repair --apply --json`
- one bounded `launch smoke --json`
- one rerun of:
  - `status --json`
  - `healthcheck --json`
  - `accounts list --json`
  - `rollout rotation inspect --json`
- factual go/no-go decision for posture-normalization readiness

Out of scope:
- `accounts ...` mutations
- `policy stage set`
- `rollout stage advance 20`
- repo repair
- manual file edits outside audit artifacts
- UI work

Assumptions:
- `step40` proved stale rotation was only the first blocker
- `step40` and independent inspectors proved the remaining contradiction is
  downstream of policy drift, not a rotation-owner bug
- `stable repair --dry-run --json` already showed a valid exact approved-set
  reconciliation plan

Truth ownership:
- `policy_drift` owner truth = `status --json`
- `policy_drift_observed` owner truth = `status --json`
- rotation participation truth = `rollout rotation inspect --json`
- runtime attestation truth = `healthcheck --json`
- approved-target reference truth = `stable target switch --json`
- approved-target inventory truth = `stable repair --json`

Acceptance criteria:
- `stable repair --apply --json` returns strict JSON and reconciles the approved
  target inventory without contract drift
- `launch smoke --json` returns strict JSON and records approved-target
  activation evidence
- post-apply `status --json` no longer reports top-level
  `policy_drift.status=detected`
- post-apply `rollout rotation inspect --json` no longer returns
  `ROTATION_EVIDENCE_CONTRADICTED`
- `healthcheck --json` remains green enough
- contour closes with factual artifacts and an explicit next action

Stop conditions:
- invalid JSON from any owner surface
- target-switch or stable-repair contract drift
- `launch smoke --json` fails
- top-level `policy_drift` remains detected after bounded apply + smoke
- `rollout rotation inspect --json` remains contradicted after bounded apply + smoke
- any need to mix posture normalization into this contour

Artifacts:
- `audit_results/step41_contour_plan.md`
- `audit_results/step41_operation_declaration.md`
- `audit_results/step41_target_switch_packet.json`
- `audit_results/step41_stable_repair_packet.json`
- `audit_results/step41_launch_smoke_packet.json`
- `audit_results/step41_owner_surface_capture.json`
- `audit_results/step41_decision_packet.json`
- `audit_results/step41_closeout_report.md`
