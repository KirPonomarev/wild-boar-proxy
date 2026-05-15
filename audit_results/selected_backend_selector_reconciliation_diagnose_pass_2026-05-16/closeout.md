# SELECTED_BACKEND_SELECTOR_RECONCILIATION_DIAGNOSE_PASS Closeout

## Goal

Determine whether the current divergence between selector-side participation
surfaces and stable policy/source-copy truth is a real selector contradiction,
expected scope divergence, staleness, or insufficient evidence, and name the
next exact contour accordingly.

## Result

- status: `completed`
- final verdict: `GO_TO_STABLE_POLICY_SOURCE_RECONCILIATION_PASS`
- next action: reconcile the approved target family against the current
  owner-path stable policy/source-copy family before reopening selector or
  exact-source admission

## Contour Capsule

- goal: localize why selected-backend participation truth, approved target
  family truth, and current stable policy/source-copy truth diverge
- branch: `codex/external-agent-lab-isolated`
- head: `cc9062a Stop auth-ref selector admission on contradicted evidence`
- touched files:
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/*`
- tests run:
  - read-only owner-path inspection only
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy stable repair --dry-run --json`
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_contradicted_for_policy_drift tests.test_cli.CliTests.test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready tests.test_cli.CliTests.test_stable_repair_dry_run_reports_materialized_approved_target_after_apply`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - exact-source admission remains unearned
  - approved target family is not the current runtime-ready family
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - policy-drift contradiction remains machine-readable in rotation evidence
  - status truth keeps approved-target-not-ready separate from effective
    observed-source runtime truth
  - stable repair dry-run continues to report approved target and current
    policy/source-copy family separately
- build:
  - `git diff --check`
- manual:
  - `selected_backend_snapshot` basenames matched `stable-repair-target`
    inventory exactly
  - current owner-path eligible source-copy family contained 11 entries
  - approved target family contained 9 entries
  - approved target missed `k-gpt-pro`, `new-new55555`, and `kp8750410-team`
  - approved target still contained `k-gpt-pro-3k`, which is not currently
    owner-eligible
  - `status --json` reported desired/effective source as
    `observed_stable_inventory_source` because approved target is not ready for
    runtime consumption
  - no secret payload contents were read
- live verification:
  - not applicable; this contour is diagnose-only and performs no secret-bearing
    action or onboarding rerun

## Artifacts

- spec:
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/stop_basis.json`
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/selector_surface_inventory.json`
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/divergence_classification.json`
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/contradiction_localization.json`
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/canon_next_step_matrix.json`
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/selected_backend_selector_reconciliation_diagnose_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only machine-readable metadata, paths, counts, and owner-path packets were inspected`

## Notes

- blockers encountered:
  - a mutation lock was held during `stable repair --dry-run --json`, but the
    owner packet still emitted a full transaction plan sufficient for this
    read-only diagnosis
- follow-up contour:
  - `STABLE_POLICY_SOURCE_RECONCILIATION_PASS`
- resume from here: `reconcile the approved repair-target family against the current owner-path policy/source-copy family before reopening selector or exact-source admission`
