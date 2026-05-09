# UI Desktop HTML App Launcher Closeout

## Contour

- `UI_DESKTOP_HTML_APP_LAUNCHER`
- Branch: `codex/ui-desktop-html-app-launcher`
- Base: `codex/ui-desktop-html-overview-full-implantation`

## Result

Implemented a terminal launcher entrypoint for the first Overview screen:

`python3 -m wild_boar_proxy.desktop_ui.app`

The launcher prepares the live snapshot, starts the safe transport, starts a
bounded static renderer service, and prints a structured startup packet. Browser
opening is not the default product path; it requires explicit
`--open-dev-preview`.

## Boundaries

- Static renderer service binds only to `127.0.0.1`.
- Static renderer serves only `wild_boar_proxy/desktop_ui`.
- Static renderer allows only `GET` and `HEAD`.
- Static renderer does not provide directory listing.
- Launcher stops only launcher-owned services.
- Launcher does not change runtime command meanings.
- Launcher does not integrate other render screens.
- Current environment has no admitted embedded renderer dependency, so the
  expected status is `embedded_unavailable_dev_preview`.

## Verification

- `python3 -m json.tool audit_results/ui_desktop_html_app_launcher_packet.json`
- `python3 -m py_compile wild_boar_proxy/desktop_ui/app.py tests/test_desktop_ui_app_launcher.py`
- `python3 -m unittest tests.test_desktop_ui_app_launcher tests.test_desktop_ui_command_adapter tests.test_desktop_ui_overview_actions tests.test_desktop_ui_overview_bridge tests.test_desktop_ui_overview_implantation tests.test_desktop_ui_overview_live_binding tests.test_desktop_ui_overview_transport tests.test_desktop_ui_static`
- `python3 -m wild_boar_proxy.desktop_ui.app --help`
- `python3 -m wild_boar_proxy.desktop_ui.app --smoke`
- `ps -axo pid,command | rg 'desktop_ui\\.app|http\\.server|overview_transport' | rg -v 'rg'`
- `rg -n "shell=True|Popen|os\\.system|rollout stage|policy stage|evidence capture|stable target switch|backend-registry|supervisor-state|runtime\\.py|cli\\.py" wild_boar_proxy/desktop_ui tests/test_desktop_ui_app_launcher.py`

Verification result: pass.

## Independent Inspection

Independent inspection confirmed:

- `runtime.py`, `cli.py`, `web_ui.py`, and `ui_shell.py` are untouched.
- Default launcher behavior does not auto-open the dev-preview.
- Static server is localhost-only, bounded to `wild_boar_proxy/desktop_ui`,
  `GET`/`HEAD` only, and rejects traversal/listing.
- Verification claims match the test files and audit packet.

Residual risks:

- If `pywebview` becomes available, the embedded renderer path auto-opens by
  design when not in smoke mode.
- Overview URL construction must stay aligned with `overview_transport.py` and
  `overview.js`.
- Static serving rules must be rechecked if the allowed file scope expands.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_VISUAL_QA_PASS` after this contour is closed.
That next contour compares the first screen against the design render and fixes
only first-screen visual regressions.
