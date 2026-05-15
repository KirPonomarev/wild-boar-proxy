# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS Closeout

## Goal

Prove reserve-first sandbox onboarding through `accounts onboard --json` without leaving `/Users/kirillponomarev/.codex-custom-test`, and only accept success if packet-plus-refresh evidence shows a newly admitted backend in `reserve` with no active-routing change.

## Result

- status: completed with blocker localization
- final verdict: STOP_AND_DIAGNOSE
- next action: repair and materialize a sandbox-safe owner onboarding lane before rerunning this contour

## Contour Capsule

- goal: execute the first sandbox-local onboarding mutation and prove `reserve_first_enforced = true` through command packet plus refresh
- branch: `codex/external-agent-lab-isolated`
- head: `278f8c9 Finalize sandbox binding closeout metadata`
- touched files: `audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/*`
- tests run: sandbox `accounts list --json` pre-snapshot; sandbox `accounts onboard --json --auth-ref /Users/kirillponomarev/.codex-custom-test/auth.json --non-interactive`; forbidden live-path drift comparison; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: sandbox-local owner onboarding binaries and post-proof helpers are missing; live owner binaries are hardwired to `/Users/kirillponomarev/.codex-custom-cli` and `/Users/kirillponomarev/.cli-proxy-api`
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests: `accounts list --json` returned an empty but valid sandbox registry snapshot; onboarding command returned `machine_error_code = MISSING_ONBOARD_BIN` with `changed_files = []`; `forbidden_drift_check.json` stayed unchanged for `/Users/kirillponomarev/.codex-custom-cli/managed/{backend-registry.json,supervisor-state.json}` and `/Users/kirillponomarev/.cli-proxy-api/config.yaml`
- build: not applicable
- manual: inspected the only available external owner binaries under `/Users/kirillponomarev/.codex-custom-cli/managed/bin/` and confirmed hardcoded `Path.home()` / `~/.codex-custom-cli` / `~/.cli-proxy-api` surfaces
- live verification: UI/result phase intentionally skipped because command-phase blocker already decided the contour honestly

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/risk_matrix.md`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts record path metadata, hashes, and machine packets only, without copying raw auth contents or logs

## Notes

- blockers encountered: the sandbox-local onboarding owner lane is incomplete, and using the available live owner binaries would violate sandbox isolation
- follow-up contour: `STOP_AND_DIAGNOSE: SANDBOX_OWNER_ONBOARDING_BINARY_ISOLATION_REPAIR_PASS`
- resume from here: `STOP_AND_DIAGNOSE: SANDBOX_OWNER_ONBOARDING_BINARY_ISOLATION_REPAIR_PASS`
