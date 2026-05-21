<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: External Models Sidecar Is A Bounded Compatibility Adapter, Not A Second Engine

## Status

Proposed

## Date

2026-05-12

## Context

Wild Boar Proxy canon keeps `CLIProxyAPI` as the engine and treats Wild Boar
Proxy as the managing layer. The external-models lab proved there is product
value in route-based external API model management, but `MASTER_PLAN.md` still
assigns local proxy servers, HTTP API surface, OpenAI-compatible endpoints, and
provider protocol translation to engine ownership. This decision is expensive to
reverse because an uncontrolled merge would create a second hidden engine and a
new runtime truth surface.

## Decision

We introduce external-models first as a bounded compatibility adapter contract.

- The sidecar is optional.
- The sidecar is local-only.
- The sidecar is not runtime truth.
- The sidecar is not Gate A input.
- The sidecar does not own accounts, rollout, or stable state.
- Provider translation is allowed only inside the bounded compatibility adapter.
- `CLIProxyAPI` remains the engine.
- Wild Boar manages lifecycle, policy, diagnostics, and command surfaces only.

## Alternatives Considered

1. Merge the external lab directly into the runtime.
   Rejected because it duplicates engine ownership and conflicts with the master
   plan boundary.
2. Reject external models entirely.
   Rejected because it throws away validated product value that can be recovered
   safely through a bounded control-layer contract.

## Consequences

- Positive:
  - We can build foundation contracts without claiming live runtime integration.
  - We avoid false HOLDs from provider health and VPN variability.
  - We preserve a path to Codex Desktop compatibility without mutating config in
    C1.
- Negative:
  - C1 does not deliver a live sidecar.
  - Sidecar lifecycle and provider validation remain gated to later contours.
- Follow-up work:
  - C2 lifecycle and mocked status
  - C3 provider diagnostics and live validation

## Evidence

- spec:
  - `EXTERNAL_MODELS_C1_FOUNDATION_SPEC.md`
- tests:
  - `tests/test_external_models.py`
  - `tests/test_cli_external_models.py`
- runtime packet:
  - none in C1
- supporting docs:
  - `MASTER_PLAN.md`
  - `COMMAND_API.md`
  - `EXTERNAL_AGENT_LAB.md`
