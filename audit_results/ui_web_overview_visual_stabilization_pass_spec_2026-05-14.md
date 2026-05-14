<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Overview Visual Stabilization Pass

## Objective

Bring the web Overview screen closer to the approved design package visual baseline while preserving runtime truth, command boundaries, and existing UI action contracts.

## In Scope

- Overview shell composition at the 1600x1000 working viewport.
- Locked brand mark replacement from the approved local design source.
- Phosphor regular icon assets for Overview navigation and visible Overview actions.
- Product-facing header simplification with a compact source pill.
- Preview-only source and state controls moved into a quieter operator strip.
- Overview card density, KPI row, events surface, and compact last-action surface.
- Browser screenshots for healthy, degraded, down, stale, and live integration failure states.
- Existing web UI tests adjusted only for intentional visual guard changes.

## Out of Scope

- Runtime behavior changes.
- Command adapter changes.
- Live server allowlist changes.
- Desktop renderer, packaging, or command bridge work.
- New live actions or widened action payloads.
- Full design-package import into the repository.
- Full icon archive import into the repository.

## Constraints

- The strict JSON command surface remains the source of truth.
- UI cannot infer success from cached state, logs, or visual state.
- Existing `id` bindings used by `overview.js` must remain available.
- Existing `data-ui-action` values for admitted Overview actions must remain unchanged.
- Live integration failure must not be rendered as healthy zero data.
- No external reference-service names, URLs, tokens, or install traces may enter repo files.

## Assumptions

- `/Users/kirillponomarev/Downloads/дикий кабан.png` is the locked boar mark source referenced by the design manifest.
- The design package working frame is 1600x1000 and export frame is 3200x2000.
- The icon package canonical format for this design package is `PNGs/regular`.
- `pulse.png` is the Phosphor package asset for the requested activity/pulse icon role.

## Acceptance Criteria

- [x] Overview fits the first 1600x1000 screenshot without obvious viewport spill.
- [x] Header has one product primary action and no prominent dev selectors.
- [x] Preview source/state controls remain available but visually secondary.
- [x] Locked logo is byte-identical to the approved local source file.
- [x] Overview navigation and visible Overview actions use Phosphor regular image assets.
- [x] KPI cards show data and no-data notes distinctly.
- [x] Last action remains compact and does not become a debug dump.
- [x] Demo healthy, degraded, down, stale, and live integration failure screenshots are captured.
- [x] Runtime, command adapter, live server, and desktop files are untouched by this contour.

## Verification

- tests: `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- manual: Browser screenshots at `audit_results/ui_web_overview_visual_stabilization_pass_screenshots/`
- live evidence: live read-only integration failure screenshot shows error/no-data state without reusing healthy data.

## Open Questions

- Whether the preview source/state strip should later move fully into a settings or developer popover across all screens.
- Whether hidden non-Overview header buttons should migrate to Phosphor in the next screen-specific contours.
