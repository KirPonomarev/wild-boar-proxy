<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Desktop UI Overview

This directory contains the desktop HTML renderer slice for
`01_overview_dashboard`.

Rules for the browser renderer boundary:

- no direct live commands
- no direct command adapter import
- no runtime file reads
- no log parsing
- no runtime truth ownership

The visual baseline is:

`/Users/kirillponomarev/Desktop/кабан дизайн/эталон дизайна.zip`

The first implementation target is:

`wild_boar_proxy_redesign/html/01_overview_dashboard.html`

Fixtures are synthetic JSON shaped like command packets. They are not generated
from live state, logs, registry files, or runtime files.

Preview fixture variants with:

`http://127.0.0.1:<port>/index.html?fixture=overview_degraded`

Preview an explicit live snapshot with:

`python3 -m wild_boar_proxy.desktop_ui.live_overview --output wild_boar_proxy/desktop_ui/live/overview_live_snapshot.json`

`http://127.0.0.1:<port>/index.html?mode=live`

The live browser path reads only the generated snapshot file. It does not run
commands from JavaScript.

Run an admitted backend-only overview action with:

`python3 -m wild_boar_proxy.desktop_ui.overview_actions switch_stable --confirmed`

This action runner is not browser click wiring. It accepts fixed action IDs,
uses `command_adapter.py`, and regenerates the live overview snapshot after the
action. Browser buttons remain deferred until a separate renderer bridge contour.

Run a backend bridge contract operation with:

`python3 -m wild_boar_proxy.desktop_ui.overview_bridge --request-json '{"operation_id":"refresh_overview"}'`

The bridge accepts fixed operation IDs only. It does not let the browser choose
commands, argv, paths, environment variables, or working directories.

Safe transport status:

`OVERVIEW_SAFE_TRANSPORT=ADMITTED_LOCAL_ONLY`

`overview_transport.py` admits a localhost-only desktop transport for fixed
`overview_bridge` JSON requests:

`POST http://127.0.0.1:<port>/overview-bridge`

The transport is not a public web app, not a general API, and not runtime truth.
It delegates only to `overview_bridge.run_bridge_request`, rejects forbidden
request fields before bridge execution, and does not read state files or logs.

The browser still defaults to the simulated lifecycle until a separate full
implantation contour wires the renderer to this admitted transport. Preview the
simulation with:

`http://127.0.0.1:<port>/index.html?mode=live&bridge=simulated`

This mode builds fixed bridge request objects and renders lifecycle states, but
it does not call backend commands from the browser.

## Command Adapter Boundary

`command_adapter.py` is a backend-side utility. Browser JavaScript does not
import it directly.

Adapter rules:

- allowlisted command IDs only
- argv-list execution only
- strict JSON packet parsing
- invalid JSON is integration failure
- stderr is support detail only
- no persistent truth cache
- no state-file or log fallback
