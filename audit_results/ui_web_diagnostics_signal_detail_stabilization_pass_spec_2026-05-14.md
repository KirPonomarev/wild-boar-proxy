<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_DIAGNOSTICS_SIGNAL_DETAIL_STABILIZATION_PASS Spec

Date: 2026-05-14
Branch: `codex/external-agent-lab-isolated`
Base head: `23747b5`

## Goal

Make `Diagnostics / Диагностика` the canonical web detail-screen: a left
signal list, a selected-object detail panel, a check chain, bounded telemetry,
latest records, and a safe support/action area.

## Scope

- Diagnostics web markup, styling, copy, and fixture/deferred source switching.
- Diagnostics-specific UI tests that previously pinned the support-package
  skeleton and line chart.
- Phosphor PNG icons needed for the visible Diagnostics UI.
- Baseline and after screenshots for the required state matrix.

## Non-Scope

- No runtime changes.
- No command adapter changes.
- No live-server allowlist changes.
- No new `ui_action` mapping.
- No new browser payload keys.
- No desktop renderer work.
- No fixture semantics changes outside the Diagnostics visual representation.
- No direct reads of logs, runtime files, state files, bundle contents, or
  private local paths from the browser UI.

## Canon Decisions

- `export_diagnostics` remains the only active Diagnostics action. It is still
  a support artifact action and does not affect primary runtime truth.
- `Полная проверка`, lifecycle controls, human-open journal, and danger action
  are displayed only as disabled/deferred controls. They do not dispatch.
- The live Diagnostics history state is deferred/no-data because there is no
  admitted bounded live history packet in this contour.
- The old line chart was replaced with a CSS tick-scale telemetry surface.
  The scale is fixture/demo-only unless a future bounded history packet exists.
- The Diagnostics screen hides the general source pill in the header to keep
  preview instrumentation out of the product plane.

## Acceptance

- At 1600x1000 there is no horizontal overflow.
- `main.scrollHeight <= main.clientHeight`.
- `diagnosticsScreen.bottom <= 934`.
- Visible inline SVG count inside `#diagnosticsScreen` is `0`.
- Live readonly failure hides fixture history and shows deferred/no-data state.
- Stale state is amber and explicit, not green.
- Export remains support artifact only.
- Full check and lifecycle actions remain disabled.
- Tests and trace scans pass.
