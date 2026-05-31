# OWNER_LEGACY_RUNTIME_SURFACES_ADMISSION_PASS Closeout

## Goal

Move proven legacy owner/runtime mechanics into repo-owned code so the next web
bridge contour depends on canonical runtime surfaces instead of private local
shell history.

## Result

- status: `closed_success`
- final verdict: legacy proxy discovery, richer managed proof guardrails, and
  operator wrapper materialization are now repo-owned and covered by tests
- next action: proceed to `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`

## Contour Capsule

- goal: consolidate legacy owner/runtime helper behavior into canonical repo
  code without creating a second truth surface
- branch: `codex/external-agent-lab-isolated`
- head: `4bb5c09` base worktree before contour commit
- touched files: see concrete list below
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/sandbox_owner_helpers.py`
  - `tests/test_cli.py`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/spec.md`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/metrics.json`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/closeout.md`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/independent_audit.json`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/test-gate-summary.txt`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/runtime-surface-summary.txt`
- tests run: see concrete list below
  - `python3 -m unittest tests.test_cli -q` -> `Ran 387 tests in 194.813s OK`
  - bundled runtime python:
    `-m unittest tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q` -> `Ran 191 tests in 8.689s OK`
  - targeted wrapper/proxy/reprobe/header tests -> `13 passed`
  - deterministic sync/reprobe regression tests -> `4 passed`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> pass
  - `git diff --check` -> pass
- blocked risks: real provider OAuth and the actual web bridge remain out of
  scope for this contour; they move to the next contour
- next exact command: start `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`

## Verification

- tests:
  - `tests.test_cli`: pass
  - `tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell`: pass
  - targeted runtime/wrapper regressions: pass
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`: pass
- manual:
  - inspected repo-generated wrapper payloads and dynamic proxy candidate
    parsing against legacy behavior expectations
- live verification:
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/test-gate-summary.txt`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/runtime-surface-summary.txt`

## Artifacts

- spec:
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/spec.md`
- packet:
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/*`
- report:
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/metrics.json`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: final contour commit recorded in git log on branch `codex/external-agent-lab-isolated`
- pushed: pending push

## Scope Check

- unrelated work mixed in: no; only runtime/helper/test/artifact files for this
  contour are intended for staging
- private-data risk reviewed: yes; wrapper payloads contain no secrets and
  committed artifacts contain no runtime auth material

## Notes

- blockers encountered:
  - none that block the contour; one test expected exact header casing and was
    tightened to case-insensitive lookup because urllib normalizes the header
    name
- follow-up contour:
  - `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`
- resume from here: start `WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN`
