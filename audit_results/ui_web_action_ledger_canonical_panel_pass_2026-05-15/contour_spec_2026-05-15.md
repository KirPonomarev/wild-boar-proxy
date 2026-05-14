# UI_WEB_ACTION_LEDGER_CANONICAL_PANEL_PASS Spec

## Goal

Canonize the existing Action Ledger as a bounded current-session command result
surface. Main screens keep a compact last-action summary; detailed command
result fields live in the ledger panel and remain non-authoritative until any
required canonical refresh completes.

## Scope

- Web UI rendering and tests only.
- Harden existing `actionLedger` and compact action summary.
- Keep browser action payload bounded to admitted structured fields.
- Sanitize response-side text before rendering in compact summary or ledger.
- Preserve session-only behavior; no persistent audit history.

## Non-Scope

- No runtime edits.
- No command adapter edits.
- No allowlist changes.
- No live server changes.
- No desktop/native work.
- No raw log, raw state, raw argv, raw JSON, token, secret, or private path display.

## Acceptance

- Ledger rows are collapsed by default and readable in the closed state.
- Compact summary and ledger sanitize human messages, next action, machine code,
  support details, and special details.
- Raw dispatch fields echoed from the server are redacted before display.
- Changed files are shown only as metadata count.
- `ok` plus refresh required remains amber until refresh complete.
- Refresh failure or mismatch remains amber and not green.
- Command error and invalid JSON remain red.
- Timeout remains amber/recoverable.
- Duplicate submit is blocked without a second dispatch.
- Screenshots and tests capture the critical states.
