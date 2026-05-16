<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_APP_COPY_LAUNCH_PASS

## Goal

Add one safe web action for launching an isolated copy, with preflight-first
admission, truthful UI states, and no browser-supplied path or current-session
overlap.

## Scope

- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`

## Decision

- keep `launch_client_dispatch` as the bounded action surface
- require server-owned isolated-copy preflight before availability or dispatch
- deny app-bundle launch targets for this contour because they do not prove a
  separate process
- keep browser payload bounded to `ui_action` only
- sanitize launch results so UI receives launch phase + preflight summary, not
  raw paths or profile context

## Expected Truth

- `preflight passed` is not `running`
- `launch requested` is not `process confirmed`
- `process confirmed` is only shown when packet evidence reports detached
  executable spawn with observed dispatch
- if preflight is missing or unsafe, launch stays blocked and UI reports why
