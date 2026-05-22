<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RUNTIME_LAUNCHER_OWNER_PROCEDURE_SERIALIZATION_FIX_PASS Closeout

## Goal

Narrow the shared lock window around launcher-backed runtime procedures so long
launcher subprocess execution no longer blindly blocks selector refresh, while
keeping generated config and launcher handoff correct.

## Result

- status: `closed_success`
- final verdict:
  `SHARED_LOCK_WINDOW_NARROWED_WITH_SEPARATE_LAUNCHER_PROCEDURE_LOCK`
- next action: move to `WEB_SAFE_APP_COPY_LAUNCH_PASS`

## Contour Capsule

- goal: remove blind collision between launcher subprocess hold time and shared
  selector/runtime mutation lock
- branch: `codex/external-agent-lab-isolated`
- head: `63d101e2dc7448b031fd7b26bc745fd196c83199` verification head before this closure-pass commit
- implementation commit: `70600534ab60f5b75c0252e0d0479c9f8816b038`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_cli.py`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/contour.md`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/decision_packet.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/closeout.md`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/proof.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/redaction_audit.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/independent_audit.json`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_stable_runtime_launcher_attempt_does_not_hold_shared_sync_lock tests.test_cli.CliTests.test_stable_runtime_launcher_attempt_serializes_concurrent_launcher_runs`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_sync_clears_stale_lock_and_proceeds_past_lock_gate tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_status_reports_stable_policy_drift_without_greenwash tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot tests.test_cli.CliTests.test_launch_smoke_reports_stable_runtime_consumer_contract tests.test_cli.CliTests.test_launch_smoke_activates_approved_target_via_generated_config_and_status_reports_effective_target tests.test_cli.CliTests.test_launch_smoke_records_conservative_observed_source_fallback_when_launcher_exits_nonzero_during_approved_target_attempt tests.test_cli.CliTests.test_launch_smoke_requires_managed_stability_window tests.test_cli.CliTests.test_launch_smoke_uses_bounded_default_stabilization_window`
  - `python3 -m json.tool audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no live retry proof was taken in this contour by design
  - top-level runtime behavior still requires later product contour verification through the web
- next exact command:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_stable_runtime_launcher_attempt_does_not_hold_shared_sync_lock`

## Verification

- tests:
  - new launcher/sync lock-boundary tests passed
  - existing sync/status/rotation/launch smoke regression tests passed
  - 2026-05-23 closure pass reverified targeted regressions without reproducing the old shared-lock self-block lane
- build:
  - `git diff --check` passed
  - decision packet parses
- manual:
  - shared mutation lock now covers only short generated-config mutation inside
    `run_stable_runtime_launcher_attempt`
  - dedicated launcher procedure lock now covers long launcher subprocess execution
  - implementation commit `70600534ab60f5b75c0252e0d0479c9f8816b038` is present in both local HEAD and `origin/codex/external-agent-lab-isolated`
- live verification:
  - none performed in this contour

## Artifacts

- spec:
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/decision_packet.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/proof.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/redaction_audit.json`
  - `audit_results/runtime_launcher_owner_procedure_serialization_fix_pass_2026-05-16/independent_audit.json`
- report:
  - closeout plus targeted test evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `70600534ab60f5b75c0252e0d0479c9f8816b038` implemented the contour fix; this closure-pass commit records final repo truth
- pushed: `yes`; implementation commit is present on `origin/codex/external-agent-lab-isolated`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; no private runtime data added to repo artifacts`

## Notes

- blockers encountered:
  - no new runtime blocker remained; the only remaining gap was repo-policy closure state
- follow-up contour:
  - `WEB_SAFE_APP_COPY_LAUNCH_PASS`
- resume from here:
  `RUNTIME_LAUNCHER_OWNER_PROCEDURE_SERIALIZATION_FIX_PASS is closed; move next to WEB_SAFE_APP_COPY_LAUNCH_PASS; no live retry was consumed here`
