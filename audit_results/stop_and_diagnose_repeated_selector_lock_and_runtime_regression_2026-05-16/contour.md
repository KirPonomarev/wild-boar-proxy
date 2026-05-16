<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION

CONTOUR:
STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION

Goal:
Localize why canonical selector refresh repeatedly returned `LOCK_HELD` and why
post-retry runtime truth regressed to `claim_gate=blocked` and
`policy_drift=detected`, without retrying live commands again or bundling a
repair into the same contour.

Size:
M

Risk level:
high

Mode:
runtime diagnosis / evidence contour

Contour class:
diagnosis-only

In scope:
- inspect existing packets/artifacts for the latest failed selector/runtime chain
- inspect implicated code paths for lock behavior, selector snapshot refresh,
  runtime consumer truth selection, and policy drift / claim gate reporting
- inspect directly relevant tests
- produce machine-readable diagnosis artifacts

Out of scope:
- no new live retry
- no repair implementation
- no auth admission
- no onboarding rerun
- no route mutation
- no stage/pilot work
- no UI work

Governing inputs:
- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `audit_results/runtime_reproof_pass_2026-05-16_v4/*`
- `audit_results/stop_and_diagnose_selector_lock_held_2026-05-16/*`
- `audit_results/selector_refresh_owner_path_pass_2026-05-16_v3/*`
- `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/*`

Diagnosis question set:
1. Was repeated `LOCK_HELD` a stale-lock bug or a true concurrent owner-path
   contention?
2. Did failed `sync --json` mutate selector evidence or leave it unchanged?
3. Why did `status --json` re-block `claim_gate` and re-detect `policy_drift`
   after selector refresh did not complete?
4. Is the runtime regression a direct sync contradiction or a truthful fallback
   to a different policy-drift claim surface after activation evidence went
   stale?

Evidence-backed findings to verify:
- `serialized_lock(...)` raises `LOCK_HELD` only while a live holder pid is
  still alive; stale locks are unlinked and retried.
- successful `sync --json` materializes
  `selected_backend_snapshot.observed_at_utc`; failed sync does not.
- `status --json` uses the approved-target policy-drift surface only when:
  approved target is ready, activation snapshot confirms approved-target
  activation, live stable runtime is healthy, and effective consumer truth still
  matches that approved target.
- when those conditions are not met, `status --json` truthfully falls back to
  the observed auth-dir policy-drift surface, which can re-block `claim_gate`.

Files written:
- `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/contour.md`
- `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/evidence_chain.json`
- `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/decision_packet.json`
- `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/closeout.md`

Verification:
- `python3 -m unittest -q tests.test_cli.CliTests.test_sync_blocks_held_lock_without_mutation`
- `python3 -m unittest -q tests.test_cli.CliTests.test_sync_clears_stale_lock_and_proceeds_past_lock_gate`
- `python3 -m unittest -q tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot`
- `python3 -m unittest -q tests.test_cli.CliTests.test_status_reports_stable_policy_drift_without_greenwash`
- `python3 -m unittest -q tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid`
- `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot`
- independent audit of the finished diagnosis packet before git close

Acceptance criteria:
- repeated `LOCK_HELD` is classified with evidence as stale-lock or true
  concurrent contention
- selector snapshot mutation semantics are classified with evidence
- runtime regression is explained as contradiction or truthful surface fallback
- a bounded next contour is named honestly
- no repair closure or retry admission is claimed without evidence
