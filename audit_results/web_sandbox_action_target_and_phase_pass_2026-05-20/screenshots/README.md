<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Screenshot Placeholder

Raster screenshots were not captured in this contour because no local headless
browser package was present in the workspace runtime. The contour relies on:

- node-based UI execution tests for `sourcePill=Sandbox`
- HTTP verification against a live local sandbox-phase server

If a later contour installs or exposes browser screenshot tooling, replace this
placeholder with:

- readonly Quick Start with disabled actions
- sandbox Quick Start with admitted action metadata
- broken sandbox target with disabled reason
