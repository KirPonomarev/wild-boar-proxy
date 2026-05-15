# SYNC_MANAGED_MODE_WRITE_SURFACE_REPAIR_PASS Closeout

## Goal

Repair the sync-owned managed write seam that reasserted `managed` runtime
truth after selector refresh, while preserving fresh participation evidence.

## Result

- status: `completed`
- final verdict: `GO_TO_RUNTIME_REPROOF_PASS`
- next action: reprove live runtime-consumer activation now that sync no longer
  restamps managed truth

## Contour Capsule

- goal: stop default sync helper execution from retaking runtime truth into the
  managed lane while preserving nested selector freshness on the real default
  owner path
- branch: `codex/external-agent-lab-isolated`
- head: `a2dce2d`
- touched files:
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/sandbox_owner_helpers.py`
  - `/Volumes/Work/wild-boar-proxy/tests/test_cli.py`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/*`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_returns_single_json_object tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_repopulates_selected_backend_ids_from_live_capable_registry tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_sync_reports_config_toml_change_when_external_sync_promotes_base_url tests.test_cli.CliTests.test_sync_preserves_stable_runtime_truth_when_activation_evidence_exists tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - `claim_gate` remains blocked
  - approved-target activation evidence is stale for effective runtime-consumer truth
  - exact auth-source work remains unearned
- next exact command: `python3 -m wild_boar_proxy healthcheck --json`

## Verification

- tests:
  - default sync helper is reprovisioned to the repo-owned helper
  - sync success still materializes fresh selected-backend snapshots
  - explicit sync overrides remain able to mutate their own test surfaces
  - sync cannot restamp managed truth once stable activation evidence exists
  - status still clears approved-target policy drift only when live stable
    activation evidence is valid
- build:
  - `git diff --check`
- manual:
  - live `sync --json` returned:
    `machine_error_code = OK`,
    `desired_mode = stable`,
    `effective_mode = stable`,
    `endpoint = http://127.0.0.1:8318/v1`
  - live post-sync state showed:
    `selected_backend_ids = 15 live-capable active backends`
    `selected_backend_snapshot.source_name = sync --json`
  - live `status --json` returned:
    `effective_mode = stable`,
    `claim_gate = blocked`,
    `policy_drift = detected`,
    `effective_source_status = observed_source_active`,
    `consumer_activation_readiness = activation_pending`
  - live `rollout rotation inspect --json` returned:
    `machine_error_code = OK`,
    `participation_evidence_present`,
    `evidence_freshness = fresh`,
    `policy_drift_status = clear`
  - live files now show:
    `runtime-effective-mode.txt = stable`
    `config.toml base_url = http://127.0.0.1:8318/v1`
- live verification:
  - repaired sync path no longer reasserts managed truth
  - repaired repo-owned sync helper now repopulates live-capable selected backends
  - selector freshness remained intact as a valid nested snapshot even after post-sync `status --json`
  - remaining blocker is runtime reproof, not another sync or selector seam

## Artifacts

- spec:
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/repair_basis.json`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/write_surface_repair_plan.json`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/post_repair_status.json`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/post_repair_rotation.json`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/anti_loop_evaluation.json`
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only bounded machine-readable runtime and
  packet surfaces were recorded`

## Notes

- blockers encountered:
  - top-level anti-loop markers did not all clear inside this repair contour
  - `status --json` still clears the flat `selected_backend_ids` field during stable reconciliation, but preserved the valid nested selector snapshot and did not become the strongest blocker
  - the seam repair still narrowed the blocker from sync write ambiguity to runtime activation evidence only
- follow-up contour:
  - `RUNTIME_REPROOF_PASS`
- resume from here: `run runtime reproof now that sync no longer restamps managed truth`
