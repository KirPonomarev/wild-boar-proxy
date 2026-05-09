<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Desktop UI Static Overview

This directory contains the fixture-only desktop HTML renderer slice for
`01_overview_dashboard`.

Rules for this contour:

- no live commands
- no command adapter
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
