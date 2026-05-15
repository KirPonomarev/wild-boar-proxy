# SYNC_POLICY_DRIFT_SELECTOR_CONTRADICTION_DIAGNOSE_PASS Closeout

## Goal

Localize why canonical selector refresh through `sync --json` restores fresh
participation evidence but simultaneously re-blocks stable/runtime truth, then
choose the narrowest non-auth contour honestly.

## Result

- status: `completed`
- final verdict: `GO_TO_MANAGED_SYNC_MODE_DRIFT_DIAGNOSE_PASS`
- next action: diagnose why sync-managed lane truth is regressing runtime and
  re-blocking claim-gate before reopening any auth-source work

## Contour Capsule

- goal: classify whether the post-sync contradiction is stable/runtime-wide or
  lane-specific, then choose the narrowest next contour
- branch: `codex/external-agent-lab-isolated`
- head: `4630d1f`
- touched files:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/*`
- tests run:
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - claim_gate is blocked
  - effective runtime truth is managed / observed source
  - exact auth-source work remains unearned
- next exact command: `python3 -m wild_boar_proxy status --json`

## Verification

- tests:
  - sync refreshes nested selected-backend snapshot freshness
  - rotation inspect reports available participation evidence when selector
    truth is fresh and valid
  - status uses the approved-target policy-drift surface only when live
    activation evidence remains valid
- build:
  - `git diff --check`
- manual:
  - post-sync `rollout rotation inspect --json` returned `OK` with fresh
    `participation_evidence_present` and `multi_backend_snapshot`
  - post-sync `status --json` returned:
    `effective_mode = managed`,
    `claim_gate = blocked`,
    `policy_drift = detected`,
    `effective_source_status = observed_source_active`,
    `consumer_activation_readiness = activation_pending`
  - this means selector freshness improved while runtime lane truth regressed
- live verification:
  - no mutation beyond previously completed sync refresh was performed in this
    diagnose contour
  - auth-chain work remains parked

## Artifacts

- spec:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/contour.md`
- packet:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/contradiction_basis.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/surface_comparison.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/lane_classification.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/contradiction_localization.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/authority_decision.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/decision_packet.json`
- report:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16_v2/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only machine-readable owner packets,
  selected backend ids/counts, and bounded runtime path surfaces were recorded`

## Notes

- blockers encountered:
  - one earlier interpretation risked treating fresh selector evidence as more
    important than blocked claim-gate
  - final authority ranking favored runtime/claim-gate truth over selector
    freshness
- follow-up contour:
  - `MANAGED_SYNC_MODE_DRIFT_DIAGNOSE_PASS`
- resume from here: `localize why sync-managed lane activation regresses effective runtime truth after selector refresh`
