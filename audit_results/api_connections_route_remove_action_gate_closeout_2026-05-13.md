<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Route Remove Action Gate Closeout

## Goal

Implement a safe web UI action for removing an already disabled API route as a
bounded registry cleanup operation.

## Result

- status: complete
- final verdict: API_ROUTE_REMOVE_ACTION_GATE_CLOSED
- next action: choose the next contour after owner review

## Contour Capsule

- goal: implement `api_route_remove` for already disabled API routes
- branch: codex/external-agent-lab-isolated
- head: 386eb3f
- touched files: wild_boar_proxy/web_design_command_adapter.py, wild_boar_proxy/web_design_live_server.py, wild_boar_proxy/web_design_ui/scripts/overview.js, wild_boar_proxy/web_design_ui/styles/overview.css, tests/test_web_design_command_adapter.py, tests/test_web_design_live_server.py, tests/test_web_design_ui.py, audit_results/api_connections_route_remove_action_gate_spec_2026-05-13.md, audit_results/api_connections_route_remove_action_gate_matrix_2026-05-13.json, audit_results/api_connections_route_remove_action_gate_independent_audit_2026-05-13.json, audit_results/api_connections_route_remove_action_gate_closeout_2026-05-13.md
- tests run: python3 -m unittest tests.test_web_design_command_adapter; python3 -m unittest tests.test_web_design_live_server; python3 -m unittest tests.test_web_design_ui; python3 -m unittest tests.test_cli_external_models; python3 -m json.tool audit_results/api_connections_route_remove_action_gate_matrix_2026-05-13.json; python3 -m json.tool audit_results/api_connections_route_remove_action_gate_independent_audit_2026-05-13.json; python3 tools/check_closeout_resilience.py; git diff --check
- blocked risks: create/update/editor/secret/direct-file paths remain out of scope
- next exact command: git add wild_boar_proxy/web_design_command_adapter.py wild_boar_proxy/web_design_live_server.py wild_boar_proxy/web_design_ui/scripts/overview.js wild_boar_proxy/web_design_ui/styles/overview.css tests/test_web_design_command_adapter.py tests/test_web_design_live_server.py tests/test_web_design_ui.py audit_results/api_connections_route_remove_action_gate_spec_2026-05-13.md audit_results/api_connections_route_remove_action_gate_matrix_2026-05-13.json audit_results/api_connections_route_remove_action_gate_independent_audit_2026-05-13.json audit_results/api_connections_route_remove_action_gate_closeout_2026-05-13.md

## Verification

- tests:
  - `python3 -m unittest tests.test_web_design_command_adapter`
  - `python3 -m unittest tests.test_web_design_live_server`
  - `python3 -m unittest tests.test_web_design_ui`
  - `python3 -m unittest tests.test_cli_external_models`
  - `python3 -m json.tool audit_results/api_connections_route_remove_action_gate_matrix_2026-05-13.json`
  - `python3 -m json.tool audit_results/api_connections_route_remove_action_gate_independent_audit_2026-05-13.json`
  - `python3 tools/check_closeout_resilience.py`
- build: targeted Python unittest coverage
- manual:
  - checked exact adapter argv
  - checked server preflight blocks enabled and unproven route state
  - checked browser payload remains `ui_action + route_id`
  - checked UI destructive action is visually separated
- live verification: not run; this is a web-design action gate using fake runners

## Artifacts

- spec: `audit_results/api_connections_route_remove_action_gate_spec_2026-05-13.md`
- packet: `audit_results/api_connections_route_remove_action_gate_matrix_2026-05-13.json`
- report: `audit_results/api_connections_route_remove_action_gate_independent_audit_2026-05-13.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: this contour commit
- pushed: completed in the closeout cycle

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered: first test pass exposed missing explicit allowlist test and missing UI sandbox metadata; both were fixed before closeout
- follow-up contour: owner selection required
- resume from here: CLOSED / owner selects next contour
