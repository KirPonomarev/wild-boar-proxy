<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C1 Contour

```text
CONTOUR:
external_models_c1_foundation_contract

Goal:
Establish the canon-aligned external-models foundation without live provider
integration, real sidecar lifecycle, or engine duplication.

Size:
M

Risk level:
medium

Decision owner:
project owner / canon-first

Mode:
implementation

In scope:
- ADR boundary
- canonical command envelope alignment
- route schema and file lifecycle
- split config/state contracts
- isolated path overrides
- zero-test guard via real test modules

Out of scope:
- real proxy server
- live provider validation
- start/stop lifecycle
- UI
- installer automation
```
