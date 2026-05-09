<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Desktop HTML Static Overview Closeout

## Contour

`UI_DESKTOP_HTML_STATIC_OVERVIEW_WITH_FIXTURES`

## Verdict

`STATIC_OVERVIEW_WITH_FIXTURES_READY`

The first desktop HTML renderer slice now exists as a fixture-only overview
screen. It is browser-openable and does not execute live commands.

## Implemented

- `wild_boar_proxy/desktop_ui/index.html`
- `wild_boar_proxy/desktop_ui/styles/tokens.css`
- `wild_boar_proxy/desktop_ui/styles/overview.css`
- `wild_boar_proxy/desktop_ui/screens/overview.js`
- `wild_boar_proxy/desktop_ui/assets/boar_mark.png`
- synthetic overview fixtures for healthy, degraded, down, stale, unknown,
  integration failure, managed mismatch, and command error
- static safety tests in `tests/test_desktop_ui_static.py`

## Renderer Result

`pywebview` is not installed in the current environment, and no dependency was
installed in this contour.

The contour therefore proved the browser-openable static fallback with local
HTML/CSS, local asset loading, fixture switching, and a headless Chrome
screenshot at `1600x1000`.

## Scope Check

- No live command wiring.
- No command adapter.
- No runtime or CLI changes.
- No `web_ui.py` changes.
- No `ui_shell.py` changes.
- No state-file truth.
- No log parsing truth.
- No deferred rollout or stage action exposed.

## Verification

- `python3 -m unittest -q tests.test_desktop_ui_static`
- `python3 -m json.tool` for all fixture JSON files
- headless Chrome screenshot:
  - `audit_results/ui_desktop_html_static_overview_screenshot.png`
- command-safety scan:
  - no matches for `subprocess`, `Popen`, `os.system`, `~/.codex`,
    `backend-registry`, or `supervisor-state`
- `git diff --check`

## Next Contour

`UI_DESKTOP_HTML_COMMAND_ADAPTER_BOUNDARY`
