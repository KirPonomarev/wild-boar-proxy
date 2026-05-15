CONTOUR:
Goal: repair the sync-owned write surfaces that reassert managed runtime truth after selector refresh, while preserving fresh participation evidence
Size: M
Risk level: high
Decision owner: Codex
Mode: implementation

In scope:
- repo-owned default sync helper reprovisioning at bounded sync owner-path entrypoints
- repo-owned sync helper restoration of live-capable selected-backend materialization
- targeted tests for sync helper behavior and stable-truth preservation
- bounded live verification with `sync --json`, `status --json`, and `rollout rotation inspect --json`
- independent audit of post-repair contour outcome

Out of scope:
- sandbox `auth.json` materialization
- onboarding rerun
- exact auth-source admission
- selector narrowing logic redesign
- generic runtime architecture rewrite

Assumptions:
- default sync helper path is control-owned and may be reprovisioned safely
- explicit `WBP_SYNC_SCRIPT` overrides remain valid and must not be clobbered
- fresh selector evidence must survive the repair

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/sandbox_owner_helpers.py`
  - `tests/test_cli.py`
- runtime evidence:
  - pre-repair diagnose packet in `audit_results/managed_sync_mode_drift_diagnose_pass_2026-05-16/`
  - post-repair `sync --json`
  - post-repair `status --json`
  - post-repair `rollout rotation inspect --json`

Commands / files:
- `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_rotation_inspect_reads_sync_materialized_nested_snapshot tests.test_cli.CliTests.test_sync_returns_single_json_object tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_sync_reports_config_toml_change_when_external_sync_promotes_base_url tests.test_cli.CliTests.test_sync_preserves_stable_runtime_truth_when_activation_evidence_exists tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence`
- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`

Acceptance criteria:
- default sync helper no longer reasserts managed runtime truth
- default sync helper repopulates selected-backend evidence on the real owner path
- selector freshness remains fresh/present after sync
- post-repair status reports `effective_mode = stable`
- next contour is narrowed to runtime reproof or explicit stop

Verification:
- tests:
  - targeted sync/status/rotation unit tests pass
- build:
  - `git diff --check`
- manual:
  - live sync reports stable endpoint and stable effective mode
  - live status no longer overreads managed truth from repaired seam
  - live rotation evidence remains fresh, including after post-sync status verification
- live packet:
  - status/rotation packets captured after repair

Artifacts:
- spec:
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/contour.md`
- packet:
  - `repair_basis.json`
  - `write_surface_repair_plan.json`
  - `post_repair_status.json`
  - `post_repair_rotation.json`
  - `anti_loop_evaluation.json`
  - `decision_packet.json`
- closeout note:
  - `closeout.md`

Stop conditions:
- repair would require widening contracts or breaking explicit sync overrides
- selector freshness regresses after repair
- post-repair packets contradict each other in a new unresolved way

Closeout:
- verification complete: pending
- commit: pending
- push: pending
- next contour: `GO_TO_RUNTIME_REPROOF_PASS`
