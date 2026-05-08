<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step39 Contour Plan

```text
CONTOUR:
Goal:
Restore fresh and non-contradictory runtime truth before any reserve-first
posture normalization or stage-20 re-entry.

Size: M
Risk level: high
Decision owner: operator + maintainer, with disputed decisions resolved strictly
through canon order
Mode: live-proof

Canon order:
1. CANON.md
2. MASTER_PLAN.md
3. RUNTIME_CONTRACT.md
4. STATE_SCHEMA.md
5. COMMAND_API.md
6. DELIVERY_RULES.md
7. README.md

In scope:
- read-only reproof of canonical truth surfaces
- one bounded live-runtime refresh step if and only if rotation evidence is
  stale
- re-evaluation of claim_gate and policy_drift on owner surfaces
- factual go/no-go decision for posture-normalization readiness

Out of scope:
- accounts promote/demote/hold/release/retire
- policy stage set
- rollout stage advance 20
- launch smoke by default
- repo repair
- engine-layer work
- manual state or registry edits
- UI work

Assumptions:
- step38 is canonical and closed NO_GO on runtime-truth blockers
- current stage-20 branch remains LIVE_POSTURE_DRIFT_ONLY, but live posture work
  may not start until runtime truth is green enough
- sync --json is a write owner surface, not a read-only observation surface

Inputs:
- docs:
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
  - NEXT_CONTOUR_CANON_PLAN.md
  - audit_results/step38_readonly_snapshot.json
  - audit_results/step38_decision_packet.json
- code:
  - wild_boar_proxy/runtime.py
  - tests/test_cli.py
- runtime evidence:
  - fresh status --json
  - fresh healthcheck --json
  - fresh accounts list --json
  - fresh rollout rotation inspect --json

Live operation declaration:
- exact commands must be declared before execution
- exact real read paths must be declared before execution
- exact real write paths must be declared before execution
- rollback expectation must be declared before execution

Allowed execution shape:
phase 1 = read-only truth reproof
phase 2 = exactly one bounded sync refresh, only if phase 1 shows stale
rotation evidence
phase 3 = exactly one rerun of canonical read surfaces

No second sync is allowed in this contour.
No launch smoke is allowed by default in this contour.
Launch smoke may be opened only through STOP_AND_DIAGNOSE if canon-level truth
cannot otherwise be resolved.

Commands / files:
- git status --short --branch
- python3 -m wild_boar_proxy status --json
- python3 -m wild_boar_proxy healthcheck --json
- python3 -m wild_boar_proxy accounts list --json
- python3 -m wild_boar_proxy rollout rotation inspect --json
- if and only if rotation evidence is stale:
  - python3 -m wild_boar_proxy sync --json
- rerun once after bounded refresh:
  - python3 -m wild_boar_proxy status --json
  - python3 -m wild_boar_proxy healthcheck --json
  - python3 -m wild_boar_proxy accounts list --json
  - python3 -m wild_boar_proxy rollout rotation inspect --json

Truth ownership rules:
- claim_gate owner truth = status --json
- policy_drift owner truth = status --json
- runtime attestation and launch_readiness owner truth = healthcheck --json
- rotation freshness and participation owner truth = rollout rotation inspect --json
- narrative summaries, memory, and stale prior packets do not override current
  owner surfaces

Acceptance criteria:
- rollout rotation inspect --json no longer returns ROTATION_EVIDENCE_STALE
- status --json no longer reports claim_gate.status=blocked
- status --json no longer reports policy_drift.status=detected
- healthcheck --json remains launch_readiness.status=ready
- no manual mutations were used
- no more than one sync write step was executed
- the contour closes with a factual packet and explicit next action

Verification:
- tests:
  - none required for the default read/reclear path
  - if contour scope unexpectedly touches repo code, STOP_AND_DIAGNOSE and open a
    separate repo contour
- build:
  - not applicable by default
- manual:
  - compare owner-surface packets before and after bounded refresh
- live packet:
  - status --json
  - healthcheck --json
  - accounts list --json
  - rollout rotation inspect --json
  - optional sync --json packet if refresh was required

Artifacts:
- spec:
  - audit_results/step39_contour_plan.md
- packet:
  - audit_results/step39_operation_declaration.md
  - audit_results/step39_owner_surface_capture.json
  - audit_results/step39_decision_packet.json
- closeout note:
  - audit_results/step39_closeout_report.md

Stop conditions:
- any invalid JSON packet
- healthcheck --json stops being green enough
- sync --json fails
- rotation evidence remains stale after the one allowed sync
- claim_gate remains blocked after bounded refresh
- policy_drift remains detected after bounded refresh
- any need for a second sync
- any need for manual file edits
- any signal that repo repair is required to complete reclear

Closeout:
- verification complete:
  - owner-surface packets captured and compared
  - bounded refresh rules honored
- commit:
  - docs/artifact-only if repo files changed
- push:
  - required for any closed write contour
- next contour:
  - GO_POSTURE_NORMALIZATION if truth lane is green again
  - NO_GO_RUNTIME_RECLEAR_FAILED if truth lane remains blocked
  - ENGINE_BLOCKER_ESCALATION_REQUIRED if owner surfaces cannot restore truthful state
```
