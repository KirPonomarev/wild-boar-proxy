<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Diagnostics Page Operator Alignment

## Objective

Align the existing Diagnostics screen with the operator UI style already used by
the current web control panel. Keep diagnostics as support evidence only: the
screen must not create runtime truth, add live mutations, expose browser
file/path inputs, or touch command/runtime contracts.

## In Scope

- Diagnostics screen copy in `wild_boar_proxy/web_design_ui/index.html`.
- Diagnostics screen display helpers in `wild_boar_proxy/web_design_ui/scripts/overview.js`.
- Diagnostics screen density/layout CSS in `wild_boar_proxy/web_design_ui/styles/overview.css`.
- UI tests in `tests/test_web_design_ui.py`.
- Browser screenshots and factual closeout artifacts for this contour.

## Out of Scope

- `wild_boar_proxy/runtime.py`.
- `wild_boar_proxy/web_design_command_adapter.py`.
- `wild_boar_proxy/web_design_live_server.py`.
- `COMMAND_API.md` and `RUNTIME_CONTRACT.md`.
- Settings Diagnostics / Privacy subflow semantics.
- Diagnostics export implementation, support bundle generation, allowlist, or
  desktop/native bridge behavior.

## Constraints

- `export_diagnostics` remains support-artifact only.
- Diagnostics export success must never become runtime health truth.
- Live mode must not fall back to fixture history as truth.
- Browser must not accept secrets, local paths, auth files, backend ids, or file
  picker input.
- Diagnostics screen must not add new `data-ui-action` surfaces.
- Fixture/demo copy must say it is bounded and not runtime health.

## Assumptions

- This is a visual/text alignment pass under `WEB_DESIGN_FINISH_PASS`, not a new
  feature or command expansion contour.
- Existing live server metadata and command adapter contracts remain the source
  of truth for action availability.

## Acceptance Criteria

- [x] Diagnostics screen uses operator-readable Russian labels for signal list,
      chart legend, records, and blocked actions.
- [x] Live diagnostics shows deferred history/records instead of fixture truth.
- [x] Fixture diagnostics shows bounded demo history and records.
- [x] No new command surfaces, file inputs, path inputs, or live mutations exist
      in diagnostics markup.
- [x] Settings Diagnostics / Privacy contract remains untouched.
- [x] Browser at `1600x1000` has no horizontal overflow, no visible SVG icons,
      and no broken images.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`;
  `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`;
  `git diff --check`.
- build: static web UI served through `wild_boar_proxy.web_design_live_server`
  on `127.0.0.1:8767`.
- manual: in-app browser checks for live and fixture diagnostics states.
- live evidence: screenshots in `screenshots/diagnostics-live-deferred.png` and
  `screenshots/diagnostics-fixture-summary.png`.

## Open Questions

- No blocking open questions for this contour.
