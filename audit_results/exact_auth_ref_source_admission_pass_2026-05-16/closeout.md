# EXACT_AUTH_REF_SOURCE_ADMISSION_PASS Closeout

## Goal

Determine whether the current approved-target runtime and selector truth is now
enough to admit one exact auth-ref source canonically.

## Result

- status: `completed`
- final verdict: `STOP_AND_DIAGNOSE`
- next action: do not attempt exact-source admission or sandbox auth
  materialization; preserve the multi-candidate evidence and resolve the
  admission-surface mismatch before reopening this lane

## Contour Capsule

- goal: test whether exact auth-ref identity is now singleton-honest on a
  canonical machine-readable basis
- branch: `codex/external-agent-lab-isolated`
- head: `034760f`
- touched files:
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/*`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_imports_backend_to_reserve_without_sync tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_mismatch_does_not_match_by_basename tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_skip_login_mismatch_does_not_claim_success tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence`
  - `python3 -m unittest -v tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_skip_login_forwards_flag_and_runs_full_proof`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/exact_auth_ref_source_admission_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no singleton exact auth-ref basis exists in the current live packet chain
  - no separate exact-source admission CLI surface exists
  - the nearest explicit-auth owner path has a relevant failing full-proof test
- next exact command: `STOP_AND_DIAGNOSE`

## Verification

- tests:
  - five targeted accounts/status/rotation tests passed
  - one relevant explicit-auth full-proof test failed:
    `tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_skip_login_forwards_flag_and_runs_full_proof`
- build:
  - `git diff --check`
- manual:
  - `status --json` returned `claim_gate = clear`, `policy_drift = clear`,
    `effective_stable_runtime_consumer_source.status = approved_target_active_by_activation_evidence`
  - `rollout rotation inspect --json` remained green but family-level with
    `evidence_reason = multi_backend_snapshot`
  - nested `selected_backend_snapshot.selected_backend_ids` contained 15
    selected backends while flat `selected_backend_ids` remained empty
  - `accounts onboard --json --auth-ref ...` is the exposed explicit-auth owner
    surface, but the runtime success contract proves success from uniquely
    selected newly added backends only
- live verification:
  - runtime and selector supporting surfaces stayed green
  - exact source identity remained multi-candidate
  - no safe canonical admission command for one already-active auth-ref was
    available

## Artifacts

- spec:
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/admission_basis.json`
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/exact_source_evidence_comparison.json`
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/exact_source_decision.json`
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/anti_guess_evaluation.json`
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/exact_auth_ref_source_admission_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only bounded machine-readable runtime and test evidence were recorded`

## Notes

- blockers encountered:
  - earlier contour narrative referenced a nonexistent command surface:
    `python3 -m wild_boar_proxy auth ref-source admission --json`
  - current exact-source basis is still a 15-member auth-ref family
  - one relevant explicit-auth full-proof test is red on the current branch
- follow-up contour:
  - `STOP_AND_DIAGNOSE`
- resume from here: `CLOSED / STOP_AND_DIAGNOSE`
