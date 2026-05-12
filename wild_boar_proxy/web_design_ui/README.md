<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Web Design UI Preview

This directory contains the fixture-backed web transfer of the
`01_overview_dashboard` design frame from the local render package.

It is intentionally static in this contour:

- no live command execution
- no runtime/state/log file reads
- no desktop shell integration
- no replacement of `wild_boar_proxy/web_ui.py`

Fixtures imitate the expected UI input shape only. They are not runtime truth,
not evidence, and not acceptance for live binding.

Open locally with:

```sh
python3 -m http.server 8787 --directory wild_boar_proxy/web_design_ui
```

Then visit:

```text
http://127.0.0.1:8787/?state=healthy
```

Available fixture states:

- `healthy`
- `degraded`
- `down`
- `stale`
- `unknown`
- `integration_failure`
