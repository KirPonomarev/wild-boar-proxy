<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web API Connections Page Operator Alignment Pass

## Objective

Align the existing `API-подключения` read-only/deferred web page with the operator UI density already applied to Quick Start, without adding command surfaces or changing runtime behavior.

## In Scope

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_web_design_ui.py`
- Browser acceptance for `?screen=api-connections`

## Out of Scope

- Runtime changes.
- Command adapter changes.
- Live server changes.
- Route create/update/remove behavior changes.
- Canon, command contract, runtime contract, allowlist, desktop/native bridge.

## Constraints

- Preserve `data-api-connections-mode="readonly-registry"`.
- Preserve `data-api-registry-surface="readonly-list"`.
- Preserve `data-api-builder-mode="deferred"`.
- Do not add browser-submitted token, secret, path, auth, backend, or file inputs.
- Do not introduce `api_route_create`, `api_route_update`, or `api_route_draft`.
- Do not claim runtime readiness, provider health, saved config, or valid token.

## Assumptions

- This is existing UI alignment under `WEB_DESIGN_FINISH_PASS`, not rich UI expansion.
- Route actions already admitted by the server remain governed by existing metadata and `applyActionAvailability()`.
- `secret_ref` is displayed as a bounded reference label, not a secret value.

## Acceptance Criteria

- [x] API page copy is operator-facing and removes old default-view phrases `Registry enabled`, `Last check`, and `missing surface`.
- [x] Route table columns fit the viewport without page-level horizontal overflow.
- [x] Deferred route builder remains visibly deferred and disabled.
- [x] No new command surfaces are introduced.
- [x] No forbidden browser inputs are introduced.
- [x] Browser acceptance records `visibleSvgIcons === 0` and `brokenImages === []`.
- [x] Targeted tests pass.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; bundled Python `-B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- build: not applicable; static UI and Python test suite contour
- manual: in-app browser checked live and fixture `api-connections`
- live evidence: `metrics.json` and `screenshots/api-connections-live.png`

## Open Questions

- Remaining pages should be aligned in separate contours to avoid cross-screen scope mixing.
