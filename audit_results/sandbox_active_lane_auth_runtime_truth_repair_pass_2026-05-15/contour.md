# SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS

Goal: determine whether the sandbox active-lane auth/runtime blocker after failed promotion can be repaired inside the current contour without smuggling in auth-secret rotation/import or launch/materialization scope.

Size: S
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- fresh sandbox-local healthcheck/status/sync packets
- dry-run inspection of stable target-switch and stable-repair control-layer surfaces
- code/test inspection for attestation ownership and active-lane materialization rules
- independent audit

Out of scope:
- auth-secret rotation/import
- launch smoke execution
- launcher materialization execution
- lifecycle continuation into demote/hold/release/retire
- broad runtime redesign

Assumptions:
- sandbox env map from prior policy contour remains authoritative
- owner approval for sandbox-local inspection remains in force

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md
- code: wild_boar_proxy/runtime.py, wild_boar_proxy/sandbox_owner_helpers.py, tests/test_cli.py
- runtime evidence: fresh sandbox packets plus prior failed promotion packet

Commands / files:
- python3 -m wild_boar_proxy healthcheck --json
- python3 -m wild_boar_proxy status --json
- python3 -m wild_boar_proxy sync --json
- python3 -m wild_boar_proxy stable target switch --dry-run --json
- python3 -m wild_boar_proxy stable repair --dry-run --json

Acceptance criteria:
- blocker is localized with fresh machine-carried evidence
- contour either produces a narrow admissible repair or closes STOP_AND_DIAGNOSE honestly
- no live fallback or forbidden live-path drift is introduced

Verification:
- tests: targeted unittest subset
- build: not applicable, no code changes
- manual: sandbox packet inspection and listener checks
- live packet: healthcheck/status/sync/target-switch-dry-run/stable-repair-dry-run

Artifacts:
- packet: blocker_confirmation.json, truth_source_split.json, active_lane_verification.json, decision_packet.json
- report: targeted_test_report.txt, independent_audit.md, closeout.md

Stop conditions:
- live observed HTTP 401 remains truthful
- active lane remains unmaterialized after admissible inspection
- repair would require auth-secret rotation/import or launch/materialization re-scope

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: SANDBOX_ACTIVE_LANE_AUTH_SOURCE_AND_MATERIALIZATION_SCOPE_ADMISSION_PASS
