CONTOUR:
Goal:
Capture fresh owner-surface truth after `step41`, classify the current posture/
participation blocker, and issue a factual decision packet for whether a
separate live normalization contour may open.

Size: M
Risk level: high
Decision owner: operator + maintainer
Mode: live-proof

Execution identity:
- this is `step42`
- `step40` closed `NO_GO_RUNTIME_RECLEAR_FAILED`
- `step41` cleared the policy-drift contradiction but left
  `ROTATION_EVIDENCE_INSUFFICIENT`
- `step42` is a repo-write decision contour, not a live normalization contour

Canon order:
1. CANON.md
2. MASTER_PLAN.md
3. RUNTIME_CONTRACT.md
4. STATE_SCHEMA.md
5. COMMAND_API.md
6. DELIVERY_RULES.md
7. README.md
8. latest closed decision artifacts when plan wording is stale

Preconditions:
- explicit standing owner authorization is present in the active thread
- repo-side admissibility must be revalidated at contour start

In scope:
- one bounded read-only run of:
  - `status --json`
  - `healthcheck --json`
  - `accounts list --json`
  - `rollout rotation inspect --json`
- bounded contradiction recheck only if owner surfaces disagree materially
- factual go/no-go decision for opening a separate live normalization contour
- audit artifact emission under `audit_results/`

Out of scope:
- posture normalization
- `rollout stage advance 20`
- any live runtime mutation
- UI work
- installer work
- external-agent-lab progression
- manual runtime-state edits

Truth ownership:
- top-level posture truth = `status --json`
- runtime attestation truth = `healthcheck --json`
- pool posture truth = `accounts list --json`
- participation truth = `rollout rotation inspect --json`
- contradictory command output triggers `STOP_AND_DIAGNOSE`

Acceptance criteria:
- all owner surfaces return strict JSON packets
- contradiction, if observed, is preserved and boundedly rechecked
- decision packet names the blocker class and next action without silent inference
- repo artifacts are factual and scope-clean

Stop conditions:
- invalid JSON from any owner surface
- authorization gate closes
- contradictory command output remains unresolved after bounded recheck
- any need to mix normalization into this contour
- any unexpected runtime mutation

Artifacts:
- `audit_results/step42_contour_plan.md`
- `audit_results/step42_operation_declaration.md`
- `audit_results/step42_status_packet.json`
- `audit_results/step42_healthcheck_packet.json`
- `audit_results/step42_accounts_list_packet.json`
- `audit_results/step42_rotation_inspect_packet.json`
- `audit_results/step42_status_recheck_packet.json` if needed
- `audit_results/step42_rotation_recheck_packet.json` if needed
- `audit_results/step42_owner_surface_capture.json`
- `audit_results/step42_normalization_decision_packet.json`
- `audit_results/step42_decision_packet.json`
- `audit_results/step42_closeout_report.md`
