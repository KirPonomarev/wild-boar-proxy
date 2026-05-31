# SYNC_POLICY_DRIFT_SELECTOR_CONTRADICTION_DIAGNOSE_PASS Closeout

## Goal

Localize why canonical selector refresh through `sync --json` produced a fresh
snapshot but also reopened contradicted policy-drift truth, and name the
narrowest next contour honestly.

## Result

- status: `completed`
- final verdict: `GO_TO_STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
- next action: reconcile stable policy/runtime truth after the managed-lane sync
  refresh reopened policy drift and re-blocked claim-gate

## Contour Capsule

- goal: distinguish stale-selector issues from cross-lane policy/runtime drift
  after canonical sync refresh
- branch: `codex/external-agent-lab-isolated`
- head: `c1fb481 Record selector refresh contradiction`
- touched files:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/*`
- tests run:
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy stable repair --dry-run --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_contradicted_for_policy_drift`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - policy drift is active again
  - claim-gate is re-blocked
  - stable repair again has pending reconciliation work
  - exact auth-source admission remains unearned
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - sync is the canonical materialization/refresh owner for selected backend snapshot
  - selected backend snapshot refresh can succeed without earning exact-source admission
  - contradicted rotation evidence under policy drift remains machine-readable
- build:
  - `git diff --check`
- manual:
  - `sync --json` refreshed selected-backend snapshot to fresh with count `15`
  - `rollout rotation inspect --json` reported
    `ROTATION_EVIDENCE_CONTRADICTED` with `policy_drift_detected`
  - `status --json` reported `effective_mode = managed`,
    `claim_gate = blocked`, `policy_drift = detected`,
    `desired_source_kind = observed_stable_inventory_source`,
    `effective_source_kind = observed_stable_inventory_source`
  - `stable repair --dry-run --json` reported `would_change = true` with
    add-count `6` and prune-count `2`
- live verification:
  - not applicable; this contour is diagnose-only and performs no secret-bearing
    or onboarding action

## Artifacts

- spec:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/contradiction_basis.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/surface_comparison.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/lane_classification.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/contradiction_localization.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/authority_decision.json`
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/sync_policy_drift_selector_contradiction_diagnose_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only machine-readable command packets,
  selected backend ids, counts, snapshot metadata, and bounded path surfaces
  were recorded`

## Notes

- blockers encountered:
  - canonical selector refresh resolved staleness but reopened stable
    policy/runtime drift
  - rotation contradiction is now a fresh policy/runtime issue, not a stale
    snapshot issue
- follow-up contour:
  - `STABLE_POLICY_RUNTIME_RECONCILIATION_PASS`
- resume from here: `reconcile stable policy/runtime truth after sync-driven managed-lane refresh before reopening any sandbox auth-source work`
