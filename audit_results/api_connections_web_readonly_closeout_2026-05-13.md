# API Connections Web Readonly Closeout

- Contour: `API_CONNECTIONS_WEB_SCREEN_READONLY`
- Date: `2026-05-13`
- Status: `completed`
- Classification: `bounded control-surface exposure`

## Scope

- Added sidebar item `API-подключения` to `web_design_ui`.
- Added readonly `API-подключения` screen in `web_design_ui`.
- Added packet-derived `/api/api-connections-readonly` server endpoint.
- Kept `active/primary/failover/key setup/add-edit-remove route` deferred.
- Kept frontend free of direct `routes.json/state.json/secrets.env` reads.

## Files Changed

- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`

## Verification

- `python3 -m unittest tests.test_web_design_live_server`
- `python3 -m unittest tests.test_web_design_ui`
- `python3 -m unittest tests.test_web_design_command_adapter tests.test_web_ui tests.test_external_models tests.test_cli_external_models`
- `git diff --check`
- `rg -n "Вкл|Сделать активным|Основной|Непрерывный поток|сетки|Сетки" wild_boar_proxy/web_design_ui --glob '!**/*.png'`
- `rg -n "command_id|argv|shell|raw_argv" wild_boar_proxy/web_design_ui/scripts/overview.js wild_boar_proxy/web_design_ui/index.html`
- `rg -n "routes\.json|state\.json|secrets\.env" wild_boar_proxy/web_design_ui wild_boar_proxy/web_design_live_server.py`
- `rg -n "lazyweb|www\.lazyweb\.com|mcp-install|lazyweb_mcp_token|api/mcp/install-token" /Volumes/Work/wild-boar-proxy --hidden --glob '!**/.git/**'`

## Visual Smoke

- Preview server: `http://127.0.0.1:8788/?source=live&screen=api-connections`
- API smoke: `/api/api-connections-readonly`
- Screenshot captured: `/tmp/wbp-api-connections-readonly-2026-05-13.png`
- Visual check: sidebar entry visible, readonly screen rendered, no route actions shown, no forbidden `active/failover` claims on screen.

## Findings

- No new truth surface introduced.
- Readonly normalization remains packet-derived only.
- No `secret_ref`, token, or raw path leaked to browser payload.
- No forbidden copy `Вкл`, `Сделать активным`, `Основной`, `Сетки`, `Непрерывный поток` in the new screen.
- Existing unrelated `external_lab` untracked tail remained untouched and unstaged.

## Deferred

- `API_CONNECTIONS_WEB_SAFE_ACTIONS`
- `active/primary route`
- `automatic failover`
- `key setup`
- `route add/edit/remove`
