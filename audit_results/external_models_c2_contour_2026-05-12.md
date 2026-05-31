<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C2 Contour

```text
CONTOUR:
external_models_c2_lifecycle_and_mocked_status

Goal:
Add bounded synthetic lifecycle ownership for external-models above C1:
synthetic start/stop/status, local token lifecycle, reserved-port policy,
state migration, and honest non-live packets without real listener ownership.

Size:
M / L

Risk level:
medium

Decision owner:
project owner / canon-first

Mode:
implementation

In scope:
- synthetic start/stop
- status/models/profile packet upgrades
- local token lifecycle
- reserved-port protection
- state v1->v2 migration
- isolated-path verification

Out of scope:
- real listener
- provider traffic
- live validate/check
- Codex config mutation
- runtime truth integration
```
