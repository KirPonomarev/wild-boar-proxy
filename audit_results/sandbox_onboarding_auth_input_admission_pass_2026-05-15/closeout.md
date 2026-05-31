# SANDBOX_ONBOARDING_AUTH_INPUT_ADMISSION_PASS Closeout

## Goal

Choose the narrowest next onboarding auth input lane for
`accounts onboard --json` without writing auth material, rerunning onboarding,
or widening secret-bearing scope beyond the declared sandbox boundary.

## Result

- status: `completed`
- final verdict: `GO_TO_SANDBOX_ONBOARDING_AUTH_JSON_ADMISSION_PASS`
- next action: open the lane-specific admission contour for
  `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`

## Contour Capsule

- goal: choose one primary owner-lane onboarding auth input and reject the
  broader alternative
- branch: `codex/external-agent-lab-isolated`
- head: `f9c67e1 Diagnose sandbox onboarding auth candidate gap`
- touched files:
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/*`
- tests run:
  - read-only code, artifact, and sandbox-path inspection
  - independent fact-check by `Chandrasekhar`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_skip_login_forwards_flag_and_runs_full_proof tests.test_cli.CliTests.test_accounts_onboard_explicit_auth_mismatch_does_not_match_by_basename tests.test_cli.CliTests.test_accounts_onboard_exit_zero_without_new_backend_is_not_success tests.test_external_models.ExternalModelContractTests.test_paths_from_env_uses_isolated_overrides`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no upstream secret-bearing source is admitted yet
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - explicit `--auth-ref` remains an exact forwarded path lane and mismatch
    stops honestly
  - the owner lane still treats missing default auth material as a hard stop
  - env-bound runtime paths still resolve `WBP_AUTH_FILE` inside the sandbox
    root
- build:
  - `git diff --check`
- manual:
  - `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json` is still
    missing
  - `/Users/kirillponomarev/.codex-custom-sandbox-20260515/stable/` contains
    only `config.yaml`
  - the declared sandbox write surface already includes `auth.json` under the
    fresh root
  - explicit `--auth-ref` can reference paths outside the sandbox root and is
    therefore broader by default
- live verification:
  - not applicable; this contour is admission-only and performs no auth write
    or onboarding retry

## Artifacts

- spec:
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/contour.md`
- packet:
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/auth_gap_basis.json`
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/explicit_auth_ref_lane.json`
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/sandbox_auth_json_lane.json`
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/rollback_surface_matrix.json`
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/decision_packet.json`
- report:
  - `audit_results/sandbox_onboarding_auth_input_admission_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; no auth payload contents or live secret files were copied into the repo or artifacts`

## Notes

- blockers encountered:
  - this contour could narrow the primary onboarding input lane, but it did not
    and should not admit any upstream secret source yet
- follow-up contour:
  - `SANDBOX_ONBOARDING_AUTH_JSON_ADMISSION_PASS`
- resume from here: `admit the exact upstream secret source and rollback surface for /Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json before any auth materialization or onboarding rerun`
