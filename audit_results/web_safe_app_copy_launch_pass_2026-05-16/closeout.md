<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_APP_COPY_LAUNCH_PASS Closeout

## Goal

Add one safe web action for launching an isolated copy, with preflight-first
admission and truthful result states, while keeping the current working Codex
session untouched.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `ISOLATED_COPY_PREFLIGHT_GATE_ADDED_TO_BOUNDED_WEB_LAUNCH`
- next action: move to `WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS`

## Contour Capsule

- goal:
  add preflight-gated isolated copy launch to the web UI without accepting any
  browser-supplied path or broadening runtime scope
- branch: `codex/external-agent-lab-isolated`
- head: `7060053` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/contour.md`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/decision_packet.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_web_design_live_server`
  - `python3 -m unittest -q tests.test_web_design_ui`
  - `python3 -m unittest -q tests.test_web_design_command_adapter`
  - browser check against a local safe fake-runner server at `?screen=settings&section=client&source=live`
- blocked risks:
  - no real host-app launch was performed in this contour
  - app-bundle launch remains intentionally not admitted because separate-process proof is unavailable
- next exact command:
  - `python3 -m unittest -q tests.test_web_design_live_server`

## Verification

- tests:
  - live-server tests passed with launch preflight gating, path redaction, and bounded dispatch behavior
  - UI tests passed with new preflight states and confirmation flow
- build:
  - decision packet JSON parses
  - `git diff --check` must pass before commit
- manual:
  - settings client subflow now shows preflight state separately from dispatch state
  - confirmation modal shows isolated-copy preflight facts for `launch_client_dispatch`
  - action result shows `admitted` and `process_confirmed` separately from refresh state
- live verification:
  - browser click was exercised on a local safe fake-runner server
  - no real Codex app or current working session was launched or mutated

## Artifacts

- spec:
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/decision_packet.json`
- report:
  - this closeout plus unit-test and browser-check evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: atomic contour commit is created after staged verification passes
- pushed: contour branch must be pushed before closeout is final

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; launch results are sanitized and do not expose raw paths or profile context`

## Notes

- blockers encountered:
  - browser verification first failed on a hidden-selector wait, then passed after the check was corrected to wait on `hidden === true`
  - independent auditor first reported two small gaps; both were closed and re-audited to `PASS`
- follow-up contour:
  - `WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS`
- resume from here:
  `isolated copy launch is now preflight-gated and browser-click verified on a safe fake runner; next move is account-connect dry-run, not design work`
