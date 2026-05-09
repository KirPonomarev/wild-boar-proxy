# UI Desktop HTML Overview Full Implantation Closeout

## Contour

- `UI_DESKTOP_HTML_OVERVIEW_FULL_IMPLANTATION`
- Branch: `codex/ui-desktop-html-overview-full-implantation`
- Base: `codex/ui-desktop-html-overview-safe-transport`

## Result

Connected the first Overview renderer to the admitted local safe transport.

This contour makes only the first screen transport-capable. It does not import
additional renders, does not add a general API, and does not change runtime
truth or command meaning.

## Runtime Boundary

- Browser request shapes remain fixed bridge JSON objects.
- Browser actions know only admitted `action_id` values, not CLI commands.
- Transport endpoint validation requires `http:`, `127.0.0.1`, and
  `/overview-bridge`.
- Credentials, hash, and query on the transport endpoint are rejected.
- Fixture mode, live snapshot mode, and simulated bridge mode remain available.
- Transport CORS is admitted only for local `http://127.0.0.1:<port>` origins
  so the renderer can call the transport during desktop/local preview without
  opening a general API.
- Other screens remain disabled/deferred.

## Verification

- `node --check wild_boar_proxy/desktop_ui/screens/overview.js`
- `python3 -m py_compile wild_boar_proxy/desktop_ui/overview_transport.py tests/test_desktop_ui_overview_transport.py`
- `python3 -m unittest tests.test_desktop_ui_command_adapter tests.test_desktop_ui_overview_actions tests.test_desktop_ui_overview_bridge tests.test_desktop_ui_overview_implantation tests.test_desktop_ui_overview_live_binding tests.test_desktop_ui_overview_transport tests.test_desktop_ui_static`
- `python3 -m json.tool audit_results/ui_desktop_html_overview_full_implantation_packet.json`
- `rg -n "status --json|healthcheck --json|mode set|accounts promote|rollout stage|policy stage|evidence capture|stable target switch|command_adapter|overview_bridge|XMLHttpRequest|child_process|window\\.pywebview|localhost" wild_boar_proxy/desktop_ui/screens/overview.js`
- Browser visual smoke against local static server and local safe transport.

Verification result: pass.

Screenshot evidence:

- `audit_results/ui_desktop_html_overview_full_implantation_screenshot.png`

## Independent Inspection

Independent inspection confirmed:

- `runtime.py`, `cli.py`, `web_ui.py`, and `ui_shell.py` are untouched.
- Endpoint validation is strict in both `overview.js` and `overview_transport.py`.
- Browser JS does not contain raw CLI strings, `command_adapter`, `overview_bridge`,
  `window.pywebview`, `child_process`, or `XMLHttpRequest`.
- CORS remains local-origin-only for the fixed route and is not a general API.
- Other screens remain deferred.

Residual risk:

- Simulated fallback and query-param transport preview remain present, but both
  are constrained to the first screen and localhost-only validation.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_VISUAL_QA_PASS` after this contour is closed.
That next contour compares the first screen against the render and fixes only
first-screen visual regressions.
