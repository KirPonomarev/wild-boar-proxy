<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION Closeout

## Goal

Localize why canonical selector refresh repeatedly returned `LOCK_HELD` and why
post-retry runtime truth remained red on `claim_gate` / `policy_drift`, without
reopening live retries or bundling repair into the same contour.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `CONTINUE_STOP_AND_DIAGNOSE_WITH_CONCURRENT_OWNER_PATH_SOURCE_LOCALIZATION`
- next action: localize the live concurrent owner path that is acquiring
  `wild-boar-proxy.lock` before any further selector retry

## Contour Capsule

- goal: convert repeated lock/regression behavior into one bounded diagnosis
  verdict
- branch: `codex/external-agent-lab-isolated`
- head: `af8dae9` before contour changes
- touched files:
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/contour.md`
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/evidence_chain.json`
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/decision_packet.json`
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_sync_clears_stale_lock_and_proceeds_past_lock_gate tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_status_reports_stable_policy_drift_without_greenwash tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot`
  - `python3 -m json.tool audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/decision_packet.json`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - repeated live owner-path contention remains unresolved
  - selector freshness cannot advance while sync remains lock-held
  - runtime truth will continue to fall back to the observed policy surface if
    approved-target activation evidence is not re-earned freshly
- next exact command:
  - `rg -n "wild-boar-proxy\\.lock|serialized_lock|test_sync_blocks_held_lock_without_mutation|test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid" wild_boar_proxy tests`

## Verification

- tests:
  - held lock vs stale lock semantics passed
  - failed sync snapshot preservation passed
  - truthful policy-drift blocking passed
  - approved-target claim surface gating passed
  - stale selected-backend snapshot reporting passed
- manual:
  - runtime reproof v4 cleared `claim_gate` and `policy_drift` only while live
    activation evidence remained fresh
  - first selector pass stopped because runtime had already regressed before a
    clean retry
  - bounded retry stopped again on `LOCK_HELD` with no selector progress and no
    changed files
  - current evidence does not show a stale-lock cleanup bug or a failed-sync
    mutation bug
- live verification:
  - none performed in this contour

## Artifacts

- spec:
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/contour.md`
- packet:
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/evidence_chain.json`
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/decision_packet.json`
- report:
  - independent artifact-chain scan confirmed no missing packet links in the
    latest chain

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: atomic diagnosis-artifact commit is created by the closing
  orchestration after staged verification passes; final hash is reported in the
  final orchestrator response because this file is part of that commit
- pushed: closing orchestration must push this branch before declaring the
  contour closed; final push evidence is reported in the final orchestrator
  response

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; new artifacts reference repo-relative
  packets and code paths only`

## Notes

- primary diagnosis:
  - repeated `LOCK_HELD` currently looks like real concurrent owner-path
    contention, not stale-lock cleanup failure
  - post-retry red `claim_gate/policy_drift` currently looks like truthful
    fallback to the observed policy surface after approved-target activation
    evidence went stale, not like a failed sync mutating selector state
- follow-up contour:
  - `CONCURRENT_OWNER_PATH_SOURCE_LOCALIZATION_PASS`
- resume from here:
  `keep selector retry forbidden; localize the live concurrent owner path first; do not reopen UI/auth/onboarding/stage work from this diagnosis`
