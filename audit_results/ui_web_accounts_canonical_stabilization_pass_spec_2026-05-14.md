<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_ACCOUNTS_CANONICAL_STABILIZATION_PASS Spec

Date: 2026-05-14
Branch: `codex/external-agent-lab-isolated`
Base head: `697ce50`

## Goal

Make `Accounts / Аккаунты` the canonical table screen for the web UI without
changing runtime truth, command adapter rules, live-server allowlists, desktop
surfaces, or fixture semantics.

## Scope

- Accounts header hierarchy and icon source cleanup.
- Accounts filter row and summary chips.
- Accounts table geometry, row density, ellipsis behavior, and bounded scroll.
- Accounts row selection affordance with explicitly deferred bulk execution.
- Accounts row action collapse into a per-row menu while preserving existing
  bounded `ui_action` + `account_id` execution.
- Demo/live/no-data copy that does not overclaim runtime truth.
- 1600x1000 screenshot and DOM metric verification.

## Non-Scope

- No runtime, execution-core, adapter, or live-server behavior changes.
- No new command IDs, command argv templates, allowlist entries, or browser
  payload keys.
- No desktop renderer work.
- No Accounts detail page expansion beyond preserving the existing drawer.
- No onboarding success reinterpretation and no automatic lifecycle moves.
- No private reference artifacts in the repository.

## Canon Decisions

- Bulk `Проверить выбранные` stays disabled in this contour. Selection is a
  visual table affordance only; bulk lifecycle execution needs a separate
  command contract and tests before it can become active.
- Row actions move behind `dots-three`, but the drawer keeps the expanded
  action group. That preserves the existing action availability tests and avoids
  widening the contour into a detail-drawer redesign.
- Live fetch failure uses `нет данных` chips and an explicit readonly failure
  banner. It must not reuse previous healthy values or present zeroes as facts.
- The table keeps the existing `max-height: calc(100vh - 372px)` guard because
  repo tests pin it as a visual stabilization invariant.

## Acceptance

- Header has one primary Accounts action: `Добавить аккаунт`.
- `Проверить выбранные` is disabled when no rows are selected and remains
  non-executing when rows are selected.
- Main Accounts surface contains no visible inline SVG icons.
- Table rows are 58px, header cells are 42px, and card padding is
  `18px 20px 14px`.
- Row actions are exposed as a compact dots menu.
- Long error text is ellipsized in the table cell with a title.
- Live failure chips show `нет данных`.
- 1600x1000 screenshots exist for healthy, degraded, down, stale, and live
  readonly failure states.
- DOM metrics show no horizontal overflow and no main vertical spill at
  1600x1000.
- Tests and trace scans pass.
