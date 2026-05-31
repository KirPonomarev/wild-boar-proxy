# SANDBOX_ONBOARDING_AUTH_CANDIDATE_DIAGNOSE_PASS Closeout

## Goal

Localize why `accounts onboard --json` on the preserved sandbox root could not
discover an admissible auth candidate, and choose the narrowest canon-supported
next contour without writing or copying auth material.

## Result

- status: `completed`
- final verdict: `GO_TO_SANDBOX_ONBOARDING_AUTH_CANDIDATE_ADMISSION_PASS`
- next action: open a narrow auth admission contour before any auth
  materialization or onboarding rerun

## Contour Capsule

- goal: separate observed onboarding-owner auth discovery behavior from the
  next-step auth policy decision
- branch: `codex/external-agent-lab-isolated`
- head: `7932559 Stop sandbox onboarding on missing auth candidate`
- touched files:
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/*`
- tests run:
  - read-only code and artifact inspection
  - `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_onboard_exit_zero_without_new_backend_is_not_success tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_skip_login_forwards_flag_and_runs_full_proof tests.test_cli.CliTests.test_accounts_onboard_loop_mode_forwards_flag_and_keeps_reserve_first_proof`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no secret-bearing source or destination has been admitted yet
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - current onboarding stop packet stayed the truth basis
  - explicit-auth owner lane remains supported by existing tests
  - no discovery bug needed to explain the current stop
- build:
  - `git diff --check`
- manual:
  - `auth.json` is absent under the sandbox root
  - no `codex-*.json` entries exist under the current inventory root
  - `stable/config.yaml` has no `auth-dir` override
  - helper default path and snapshot inventory path were mapped separately
- live verification:
  - not applicable; this contour is diagnosis and admission only

## Artifacts

- spec:
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/contour.md`
- packet:
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/blocker_basis.json`
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/auth_candidate_discovery_map.json`
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/sandbox_auth_path_inventory.json`
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/canon_admissibility_matrix.json`
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/decision_packet.json`
- report:
  - `audit_results/sandbox_onboarding_auth_candidate_diagnose_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; no auth payload contents or raw logs were copied into artifacts`

## Notes

- blockers encountered:
  - current sandbox wave has no admitted auth material for the onboarding owner lane
- follow-up contour:
  - `SANDBOX_ONBOARDING_AUTH_CANDIDATE_ADMISSION_PASS`
- resume from here: `admit exact auth source and exact sandbox destination surfaces before any auth materialization or onboarding rerun`
