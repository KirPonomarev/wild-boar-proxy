<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_RECOVERY_ADMITTED_SESSION_ACTIONS_READY_PASS Closeout

## Goal

Expose a bounded web-operated readiness packet for already-admitted Codex Custom selected-session recovery actions: cancel selected session and cleanup owned session root.

## Result

- status: passed
- final verdict: `CUSTOM_CODEX_RECOVERY_ADMITTED_SESSION_ACTIONS_READY_PASS` is closed with machine-backed tests, browser proof, and independent audit
- next action: start a separate rollback/process-owner contour before claiming full recovery operator readiness

## Contour Capsule

- goal: bounded admitted selected-session recovery actions packet and UI workflow
- branch: codex/external-agent-lab-isolated
- head: 8ab8aeb9 before this contour commit
- touched files: wild_boar_proxy/codex_recovery_contract.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_codex_recovery_contract.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/*
- tests run: node --check overview.js; 180 recovery/session/live/UI tests; 33 operator/command tests; git diff --check; closeout resilience staged-only
- blocked risks: false-green, POST widening, browser path/auth/backend injection, rollback/process-kill/operator-ready overclaim, arbitrary path cleanup
- next exact command: start CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS only after a separate rollback-point and process-owner contract plan

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_codex_recovery_contract tests.test_codex_custom_sessions tests.test_web_design_live_server tests.test_web_design_ui -q` passed, 180 tests
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_operator_surface tests.test_web_design_command_adapter -q` passed, 33 tests
- build:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed
  - `git diff --check` passed
  - `python3 tools/check_closeout_resilience.py --staged-only` passed before staging; will be rerun after staging by the closeout gate and pre-commit hook
- manual:
  - browser proof passed through `http://127.0.0.1:8792/` with production handler and fixture command packets
  - local proof server was stopped after verification
- live verification:
  - before session: `status=blocked`, `block_reason_code=SELECTED_SESSION_REQUIRED`
  - after session create: `status=ok`, `machine_error_code=ADMITTED_SESSION_ACTIONS_READY`, `session_admitted_actions_ready=true`
  - cancel selected: `process_kill_claimed=false`
  - cleanup selected: `owned_session_root_only=true`, `arbitrary_path_accepted=false`
  - after cleanup: `status=blocked`, `block_reason_code=SELECTED_SESSION_ALREADY_CLEANED`

## Artifacts

- spec: `audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/spec.md`
- packet: `audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/browser_proof.json`
- report: `audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/verification_summary.json`
- independent audit: `audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: to be created after final staged closeout gate
- pushed: to be pushed after commit

## Scope Check

- unrelated work mixed in: no; old untracked Security, external_lab, and legacy artifacts left untouched
- private-data risk reviewed: yes; no auth value, raw backend id, route id, path, token, secret, CODEX_HOME, or HOME is accepted from browser by the new readiness endpoint

## Notes

- blockers encountered: independent audit initially flagged missing explicit scope proof for runtime plus UI mix; contour.md and spec.md now declare the bounded mix and the re-audit passed
- follow-up contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS
- resume from here: CLOSED
