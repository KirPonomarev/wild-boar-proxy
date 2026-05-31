# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS Closeout

## Goal

Prove reserve-first sandbox onboarding through `accounts onboard --json` plus post-command refresh, using the repaired sandbox owner lane and repaired auth boundary, without work-contour drift or UI overclaim.

## Result

- status: completed
- final verdict: STOP_AND_DIAGNOSE
- next action: localize and repair post-onboard status attestation before attempting `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`

## Contour Capsule

- goal: prove a real sandbox-local onboarding admission into reserve with packet + refresh evidence
- branch: `codex/external-agent-lab-isolated`
- head: `49c9734 Repair sandbox auth payload compatibility`
- touched files: `audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/*`
- tests run: sandbox `accounts list --json` pre-refresh capture; sandbox `accounts onboard --json --auth-ref /Users/kirillponomarev/.codex-custom-test/auth.json --non-interactive`; sandbox `accounts list --json` post-refresh capture; sandbox `status --json`; forbidden live-path drift comparison; targeted UI/live-server tests for onboarding no-overclaim; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: reserve-first onboarding admission is proven, but post-onboard status proof remains degraded (`ATTESTATION_FAILED`), so lifecycle admission is not yet earned
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests: onboarding packet shows `machine_error_code = OK`, `new_backend_ids = ["auth"]`, `selection_status = selected_unique_backend`, `reserve_first_enforced = true`, `validate_outcome = ok`, `sync_outcome = ok`; post-refresh accounts list shows backend `auth` in `reserve`; separate `status --json` remains `ATTESTATION_FAILED`; targeted UI/live-server tests passed
- build: not applicable
- manual: confirmed sandbox registry contains backend `auth` with `auth_ref = /Users/kirillponomarev/.codex-custom-test/auth.json` and `pool = reserve`; forbidden live-path hashes are unchanged
- live verification: `status --json` remains `ATTESTATION_FAILED` / `degraded`, and that degraded status is recorded in `status_observed` rather than hidden or overclaimed; this blocks lifecycle admission even though reserve-first onboarding itself succeeded

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/onboard_command_packet.json`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; sandbox auth path and backend admission were exercised without mutating live work-contour auth/config paths

## Notes

- blockers encountered: reserve-first admission proof succeeded, but post-onboard runtime attestation still fails with `ATTESTATION_FAILED`, so the contour cannot honestly hand off to lifecycle actions
- follow-up contour: `SANDBOX_POST_ONBOARD_STATUS_ATTESTATION_REPAIR_PASS`
- resume from here: `SANDBOX_POST_ONBOARD_STATUS_ATTESTATION_REPAIR_PASS`
