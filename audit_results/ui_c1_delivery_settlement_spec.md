<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_C1_DELIVERY_SETTLEMENT Spec

## Goal

Settle the delivery state after `UI_C1_BASIC_COMPANION_UI_REENTRY` so render
handoff can start from a clean, reviewable, canonically closed UI base rather
than from a dirty or ambiguous branch state.

## Scope

- verify `UI_C1` closeout evidence
- verify branch / push / PR facts
- verify isolated render base cleanliness
- decide whether optional baseline gaps are blockers or deferred

## Explicit Out Of Scope

- render implementation
- `web_ui.py`
- new UI features
- runtime or CLI repair
- installer / packaging

## Expected Decision

- `render_base_branch`
- `render_base_status`
- `optional_gap_blocker_status`
- `next_contour`
