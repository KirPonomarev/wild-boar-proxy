# UI_WEB_OVERVIEW_CANONICAL_POLISH_PASS Spec

Date: 2026-05-14

## Goal

Turn the web Overview screen into the canonical product baseline for the current web design phase without changing runtime behavior, command boundaries, desktop code, or adjacent screens.

## Scope

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- Overview verification screenshots under `audit_results/ui_web_overview_canonical_polish_pass_screenshots/`

## Canon Constraints

- Preserve strict command-surface IDs and `data-ui-action` hooks.
- Keep `sourcePicker`, `statePicker`, `refreshFixture`, `sourceFooter`, and `sourcePill` mounted for existing preview and test contracts.
- Do not change runtime, command adapters, live server code, desktop code, or fixture data.
- Do not add private reference artifacts or external-reference traces.

## Planned Changes

- Move preview selectors out of the main Overview plane into quiet sidebar preview instrumentation.
- Make header refresh copy neutral: `Обновить`.
- Keep one primary header action: `Запустить клиент`.
- Make the Overview banner a state notice only, without embedded controls.
- Compact the mode card into a status row plus three visible secondary actions.
- Keep `set_mode_stable` present as a hidden contract-bearing control.
- Hide the action ledger details from the compact Overview panel while keeping the ledger DOM and command truth plumbing intact.
- Keep live/demo/stale/error states visually distinct.

## Acceptance

- Overview has no `dev-operator-strip` in main content.
- Header has no `Обновить live` or `Обновить демо`.
- Required IDs and `data-ui-action` values remain present.
- Screenshots exist for fixture healthy, degraded, down, stale, and live integration failure.
- Full-page screenshot dimensions remain `1600x1000` for sampled fit checks.
- Unit tests, syntax check, diff check, closeout resilience, and trace scan pass.
