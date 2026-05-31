<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_APP_COPY_LAUNCH_PASS Closeout

## Goal

Add one safe web action for launching an isolated copy, with preflight-first
admission and truthful result states, while keeping the current working Codex
session untouched.

## Result

- status: `closed_success`
- final verdict:
  `ISOLATED_COPY_PREFLIGHT_GATE_ADDED_TO_BOUNDED_WEB_LAUNCH`
- next action: move to `WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS`

## Contour Capsule

- goal:
  add preflight-gated isolated copy launch to the web UI without accepting any
  browser-supplied path or broadening runtime scope
- branch: `codex/external-agent-lab-isolated`
- head: `b7f67f813550e1fa8493df36321ab51bc10a66b2` verification head before this closure-pass commit
- implementation commit: `955f00045d2a716045716ae41d0b62fb7edc82a4`
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/contour.md`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/decision_packet.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/closeout.md`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/proof.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/redaction_audit.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/independent_audit.json`
- tests run:
  - `python3 -m unittest -q tests.test_web_design_live_server`
  - `python3 -m unittest -q tests.test_web_design_ui`
  - `python3 -m unittest -q tests.test_web_design_command_adapter`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_cli.CliTests.test_launch_client_reports_missing_client_path_as_owner_packet tests.test_cli.CliTests.test_launch_client_rejects_nonabsolute_client_path tests.test_cli.CliTests.test_launch_client_blocks_dispatch_when_runtime_precondition_is_unhealthy tests.test_cli.CliTests.test_launch_client_treats_detached_executable_as_bounded_dispatch_only tests.test_cli.CliTests.test_launch_client_reports_exec_format_failure_as_json_packet tests.test_cli.CliTests.test_launch_client_reports_precondition_exceptions_inside_owner_packet tests.test_cli.CliTests.test_launch_client_reports_unsupported_app_bundle_shape_in_owner_packet tests.test_cli.CliTests.test_launch_client_uses_absolute_system_open_under_hostile_path`
  - browser check against a local safe fake-runner server at `http://127.0.0.1:61196/?screen=settings&section=client&source=live`
- blocked risks:
  - no real host-app launch was performed in this contour
  - app-bundle launch remains intentionally not admitted because separate-process proof is unavailable
- next exact command:
  - `python3 -m unittest -q tests.test_web_design_live_server`

## Verification

- tests:
  - live-server tests passed with launch preflight gating, path redaction, and bounded dispatch behavior
  - UI tests passed with new preflight states and confirmation flow
  - CLI launch-owner tests passed for bounded executable dispatch, unhealthy runtime block, nonabsolute-path rejection, and app-bundle handling
- build:
  - decision packet JSON parses
  - `git diff --check` passed during closure pass
- manual:
  - settings client subflow now shows preflight state separately from dispatch state
  - confirmation modal shows isolated-copy preflight facts for `launch_client_dispatch`
  - action result shows `admitted` and `process_confirmed` separately from refresh state
  - `current_session_untouched` claim is recorded as preflight-backed rather than machine-observed
- live verification:
  - browser click was exercised on a local safe fake-runner server
  - no real Codex app or current working session was launched or mutated

## Artifacts

- spec:
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/decision_packet.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/proof.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/redaction_audit.json`
  - `audit_results/web_safe_app_copy_launch_pass_2026-05-16/independent_audit.json`
- report:
  - this closeout plus unit-test and browser-check evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `955f00045d2a716045716ae41d0b62fb7edc82a4` implemented the contour; this closure-pass commit records final repo truth
- pushed: `yes`; implementation commit is present on `origin/codex/external-agent-lab-isolated`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; launch results are sanitized and do not expose raw paths or profile context`

## Notes

- blockers encountered:
  - browser-side re-verification first targeted a hidden launch button selector; the visible settings/client launch action was then used for the factual proof
  - independent auditor found one artifact overclaim: `current_session_untouched` was preflight-backed, not machine-observed; closure pass corrected that wording
- follow-up contour:
  - `WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS`
- resume from here:
  `WEB_SAFE_APP_COPY_LAUNCH_PASS is closed; launch lane is preflight-gated and browser-click reverified on a safe fake runner; next move is WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS`
