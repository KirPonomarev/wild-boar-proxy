<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API_CONNECTIONS_WEB_SAFE_ACTIONS closeout (2026-05-13)

## Scope

- Added only two API connections UI actions:
  - `api_route_validate`
  - `api_route_check`
- Kept route mutations deferred:
  - no enable/disable UI action
  - no primary/active/failover switching
  - no key/token setup controls

## Files changed

- `wild_boar_proxy/web_design_command_adapter.py`
- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `tests/test_web_design_command_adapter.py`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`

## Verification

Commands executed:

```bash
python3 -m unittest tests.test_web_design_command_adapter
python3 -m unittest tests.test_web_design_live_server
python3 -m unittest tests.test_web_design_ui
python3 -m unittest tests.test_web_ui
python3 -m unittest tests.test_external_models
python3 -m unittest tests.test_cli_external_models
python3 -m unittest tests.test_web_design_live_server tests.test_web_design_command_adapter
python3 -m unittest tests.test_web_design_ui
git diff --check
```

Result: all green.

## Guardrails and scans

Commands executed:

```bash
rg -n "Вкл|Сделать активным|Основной|Непрерывный поток|сетки|Сетки" wild_boar_proxy/web_design_ui/index.html wild_boar_proxy/web_design_ui/scripts/overview.js wild_boar_proxy/web_design_ui/styles/overview.css
rg -n "command_id|argv|shell|raw_argv" wild_boar_proxy/web_design_ui/index.html wild_boar_proxy/web_design_ui/scripts/overview.js
rg -n "routes\.json|state\.json|secrets\.env" wild_boar_proxy/web_design_ui/index.html wild_boar_proxy/web_design_ui/scripts/overview.js
git diff -- wild_boar_proxy/web_design_command_adapter.py wild_boar_proxy/web_design_live_server.py wild_boar_proxy/web_design_ui/index.html wild_boar_proxy/web_design_ui/scripts/overview.js wild_boar_proxy/web_design_ui/styles/overview.css tests/test_web_design_command_adapter.py tests/test_web_design_live_server.py tests/test_web_design_ui.py | rg -n "lazyweb|www\.lazyweb\.com|mcp-install|lazyweb_mcp_token|api/mcp/install-token|Bearer"
```

Result:

- no forbidden API-screen wording found in changed UI files
- no browser `command_id/raw argv/shell` payload wiring in changed UI files
- no direct frontend reads of `routes.json/state.json/secrets.env`
- no private reference traces in the contour diff

Note: repository-level leak scan still contains pre-existing unrelated matches in legacy/external-lab and old documents outside this contour scope.

## Acceptance summary

- Sidebar `API-подключения` screen now supports safe route checks.
- Route checks are preflighted by `external-models routes list --json` on server side.
- Disabled/missing/unsafe route targets are blocked before command execution.
- Post-action refresh is canonical and source-bound.
- Runtime truth boundary preserved (`mutates_runtime=false`, `affects_primary_truth=false`).
