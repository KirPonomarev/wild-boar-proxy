# MANAGED_SYNC_MODE_DRIFT_DIAGNOSE_PASS Closeout

## Goal

Localize why `sync`-managed lane writes retake effective runtime truth after
stable runtime activation had already been proved, then choose the narrowest
corrective contour honestly.

## Result

- status: `completed`
- final verdict: `GO_TO_SYNC_MANAGED_MODE_WRITE_SURFACE_REPAIR_PASS`
- next action: repair the sync-owned managed write-surface family that
  reasserts `managed` runtime truth after selector refresh

## Contour Capsule

- goal: identify the exact sync-owned managed write surfaces that override
  runtime truth and re-block claim-gate
- branch: `codex/external-agent-lab-isolated`
- head: `bff7e40`
- touched files:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/*`
- tests run:
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - sync-managed writes currently keep `runtime-effective-mode.txt` on `managed`
  - `claim_gate` remains blocked while those runtime truth surfaces point to
    managed lane
  - auth-source work remains unearned
- next exact command: `python3 -m wild_boar_proxy status --json`

## Verification

- tests:
  - sync success materializes the nested selected-backend snapshot contract
  - sync success refreshes selector freshness
  - status only clears policy drift from the approved target when live stable
    runtime evidence is valid
  - rotation inspect accepts fresh participation evidence independently of the
    runtime lane contradiction
- build:
  - `git diff --check`
- manual:
  - current `status --json` reports
    `desired_mode = stable`,
    `effective_mode = managed`,
    `claim_gate = blocked`,
    `policy_drift = detected`,
    `effective_source_status = observed_source_active`
  - current `rollout rotation inspect --json` reports
    `machine_error_code = OK`,
    `participation_evidence_present`,
    `evidence_freshness = fresh`,
    `policy_drift_status = clear`
  - current live files show:
    `runtime-effective-mode.txt = managed`,
    `config.toml base_url = http://127.0.0.1:8320/v1`,
    `supervisor-state.effective_mode = managed`
- live verification:
  - no new `sync --json` or `launch smoke --json` mutation was performed in this
    contour
  - bounded owner-path reads were sufficient to localize the drift

## Artifacts

- spec:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/lane_drift_basis.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/surface_ownership_comparison.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/drift_localization.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/authority_decision.json`
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only bounded machine-readable runtime
  surfaces and file paths were recorded`

## Notes

- blockers encountered:
  - selector freshness initially looked like "enough progress", but runtime
    truth surfaces still overruled it
  - the winning seam is not auth-source ambiguity; it is sync-owned managed
    truth reassertion
- follow-up contour:
  - `SYNC_MANAGED_MODE_WRITE_SURFACE_REPAIR_PASS`
- resume from here: `repair the sync-owned managed write surfaces that keep status on managed truth after selector refresh`
