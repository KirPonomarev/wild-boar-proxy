<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_API_CONNECTIONS_LIST_REVIEW_AND_POLISH_PASS Closeout

## Goal

Bring the existing API Connections / Routes List surface closer to the canonical readonly registry screen: readable route identity, separated registry/validation/secret states, safe deferred builder copy, no raw route editor, no secret values, and no primary/failover/provider-health claims.

## Result

- status: completed
- final verdict: PASS
- next action: continue to the next planned web contour after operator review

## Contour Capsule

- goal: polish API Connections readonly registry without changing runtime, command adapter, allowlist, live server contract, desktop bridge, route builder, or raw config surfaces
- branch: codex/external-agent-lab-isolated
- head: 41a9432 pre-contour parent; contour commit follows this closeout
- touched files: wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; tests/test_web_design_ui.py; audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q; git diff --check; python3 tools/check_closeout_resilience.py audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/closeout.md; visual CDP state matrix at 1600x1000
- blocked risks: raw route JSON/config editor, secret value display, active create/update builder, enabled-route remove, route actions outside ui_action plus route_id, fake runtime/provider health, primary/failover/traffic claims
- next exact command: git status --short

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed.
  - `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q` passed: 90 tests.
  - `git diff --check` passed.
- build: static web UI syntax check passed; no build system changes.
- manual:
  - CDP rendered API Connections at `1600x1000` for fixture healthy, degraded, down, stale, and static live integration failure.
  - Metrics stayed within bounds: `documentScrollWidth=1600`, `documentScrollHeight=1000`, `mainScrollHeight=942`, `screenBottom<=705`, `visibleSvgs=0`.
  - Button text fit: all API route buttons had `scrollWidth == clientWidth`.
- live verification:
  - Static-server live endpoint failure rendered `Live-readonly маршруты недоступны. Предыдущие данные не используются.`
  - Command-boundary behavior remains covered by live-server and command-adapter tests; no live runtime mutation was performed.

## Artifacts

- spec: user-approved contour text in thread
- packet: not changed
- report:
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/api_connections_state_matrix_metrics.json`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/api_connections_metrics.json`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/screenshots/api_connections_fixture_healthy_1600x1000.png`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/screenshots/api_connections_fixture_degraded_1600x1000.png`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/screenshots/api_connections_fixture_down_1600x1000.png`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/screenshots/api_connections_fixture_stale_1600x1000.png`
  - `audit_results/ui_web_api_connections_list_review_and_polish_pass_2026-05-15/screenshots/api_connections_live_integration_failure_1600x1000.png`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout authoring; final commit produced after verification
- pushed: pending at closeout authoring; push follows commit

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; UI tests and grep checks keep raw route JSON, route_config, endpoint_path, base_url, token/secret values, and private support artifacts out of the API Connections surface

## Notes

- blockers encountered: none
- follow-up contour: none from this pass; route builder/create/update and route details remain intentionally deferred surfaces
- resume from here: CLOSED
