# SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS

Goal: determine whether the post-promotion sandbox attestation blocker can be truthfully repaired inside the current contour without smuggling in auth-secret rotation/import or launch-lane scope.

Size: S
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- sandbox-local blocker confirmation
- sandbox-local status/healthcheck/sync evidence capture
- code/test inspection for promotion status proof semantics
- independent audit

Out of scope:
- auth-secret rotation/import
- launcher contour execution
- lifecycle continuation into demote/hold/release/retire
- broad runtime redesign

Assumptions:
- sandbox env map from prior policy contour remains authoritative
- owner approval for sandbox-local mutations remains in force

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md
- code: wild_boar_proxy/runtime.py, wild_boar_proxy/sandbox_owner_helpers.py, tests/test_cli.py
- runtime evidence: prior failed promote packet, sandbox-local status/healthcheck/sync packets, listener checks, external-models state

Commands / files:
- python3 -m wild_boar_proxy status --json
- python3 -m wild_boar_proxy healthcheck --json
- python3 -m wild_boar_proxy sync --json
- python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_accounts_promote_promotes_reserve_backend_with_verified_active_routing tests.test_cli.CliTests.test_sync_reports_config_toml_change_when_external_sync_promotes_base_url tests.test_cli.CliTests.test_status_reports_default_launcher_provisioning_available_before_materialization

Acceptance criteria:
- blocker is localized with machine-carried evidence
- contour either produces a narrow admissible repair or closes STOP_AND_DIAGNOSE honestly
- no live fallback or forbidden live-path drift is introduced

Verification:
- tests: targeted unittest subset
- build: not applicable, no code changes
- manual: sandbox-local packet inspection and listener checks
- live packet: status --json, healthcheck --json, sync --json under sandbox env

Artifacts:
- packet: blocker_confirmation.json, attestation_matrix.json, status_attestation_verification.json, decision_packet.json
- report: targeted_test_report.txt, independent_audit.md, closeout.md

Stop conditions:
- live observed HTTP 401 remains truthful
- repair would require auth-secret rotation/import or launch-lane scope expansion
- managed active-lane truth cannot be earned inside current contour

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS
