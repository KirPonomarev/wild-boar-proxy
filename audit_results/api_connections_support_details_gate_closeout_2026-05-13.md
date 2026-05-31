<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API_CONNECTIONS_SUPPORT_DETAILS_GATE Closeout

## Goal

Expose support-only API route details actions on the `API-подключения` web design
screen:

- `api_route_profile`
- `api_route_evidence_capture`

The contour keeps these actions behind strict JSON command surfaces and does
not create runtime, listener, Codex config, selected-route, or automatic
route-switching truth.

## Result

- status: complete
- final verdict: pass
- next action: `API_CONNECTIONS_ROUTE_CONFIG_ADMISSION`

## Verification

- tests:
  - `python3 -m unittest tests.test_web_design_command_adapter`
  - `python3 -m unittest tests.test_web_design_live_server`
  - `python3 -m unittest tests.test_web_design_ui`
  - `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
  - `python3 -m unittest tests.test_web_ui tests.test_cli_external_models tests.test_external_models -q`
  - `python3 -m unittest discover -s tests -p 'test*.py' -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - HTTP smoke started a local `ThreadingHTTPServer` with fake strict JSON packets.
  - `/?source=fixture&screen=api-connections` returned the API screen.
  - `/api/actions` exposed `api_route_profile` and `api_route_evidence_capture`.
  - `/api/action` returned `ok` for both new actions.
  - Profile packet returned non-mutating and non-ready flags.
  - Evidence packet returned local support artifact metadata with
    `network_dependent_evidence=false`.
- live verification:
  - no real provider route, Codex config, runtime, or desktop mutation was
    authorized or executed.

## Artifacts

- spec: contour plan in thread
- packet: `audit_results/api_connections_support_details_gate_matrix_2026-05-13.json`
- packet: `audit_results/api_connections_support_details_gate_http_smoke_2026-05-13.json`
- report: `audit_results/api_connections_support_details_gate_independent_audit_2026-05-13.json`
- report: this closeout note

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no; existing external-lab tail was not staged
- private-data risk reviewed: yes; private external reference service trace scan returned no matches
- runtime.py touched: no
- desktop files touched: no
- browser path/token/raw route config payload added: no
- direct route/state/secret/evidence file read added: no
- Codex config mutation added or claimed: no
- selected-route or automatic route-switching product claim added: no

## Notes

- blockers encountered: independent audit initially failed on forbidden route-switching wording in a negative claim; wording was removed and the post-fix audit passed.
- browser engine smoke: not run because Playwright/browser automation was unavailable in this runtime; HTTP smoke plus JS VM/unit coverage was used instead and this limitation is preserved as residual risk.
- follow-up contour: `API_CONNECTIONS_ROUTE_CONFIG_ADMISSION`
- resume from here: `API_CONNECTIONS_ROUTE_CONFIG_ADMISSION`
