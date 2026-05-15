# SANDBOX_OWNER_ONBOARDING_BINARY_ISOLATION_REPAIR_PASS Closeout

## Goal

Repair the missing sandbox owner onboarding lane so that sandbox-local onboarding can resolve admissible owner helpers without touching live work-contour binaries or live auth/config paths.

## Result

- status: completed
- final verdict: GO_TO_RERUN_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS
- next action: rerun `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`

## Contour Capsule

- goal: materialize and verify a sandbox-safe owner helper chain for onboarding, validation, status, and sync
- branch: `codex/external-agent-lab-isolated`
- head: `709881d Audit sandbox onboarding reserve-first blocker`
- touched files: `wild_boar_proxy/runtime.py`; `wild_boar_proxy/sandbox_owner_helpers.py`; `tests/test_cli.py`; `audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/*`
- tests run: targeted `py_compile`; 6 targeted CLI tests covering installer helper materialization and onboarding invariants; sandbox `installer init --json`; sandbox installer idempotence check; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: helper lane is now admissible, but the real onboarding mutation proof still belongs to the rerun contour
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests: `audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/targeted_test_report.txt` shows 6 targeted tests `OK`; `py_compile` passed for runtime, helper module, and CLI tests
- build: not applicable
- manual: verified the materialized sandbox helper scripts carry repo-managed markers, point to `wild_boar_proxy.sandbox_owner_helpers`, and contain no `.codex-custom-cli` or `.cli-proxy-api` literals
- live verification: sandbox `installer init --json` materialized only sandbox-local helper paths and a second installer pass returned `changed_files = []`

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/repair_plan.md`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; the repair materialized helper wrappers only, and artifacts store path metadata plus command packets without copying raw auth contents

## Notes

- blockers encountered: none after repair design landed; the original blocker `MISSING_ONBOARD_BIN` is now replaced by a materialized repo-owned helper lane
- follow-up contour: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
- resume from here: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
