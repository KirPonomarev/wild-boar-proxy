# UI Web Accounts Read-Only Screen Contour

Date: 2026-05-12

Contour ID: `UI_WEB_ACCOUNTS_READONLY_SCREEN`

## Goal

Add the `Аккаунты` web-preview screen as an account visibility surface backed by
the canonical accounts JSON packet, without enabling account lifecycle actions,
desktop transfer, direct state/log reads, or execution-core changes.

## Scope

In scope:

- web renderer navigation from overview to accounts
- accounts table and summary chips based on the design package shape
- fixture-backed accounts rendering
- live read-only accounts rendering through `/api/accounts-readonly`
- server-side account redaction and minimized response shape
- tests for read-only command usage, redaction, invalid packets, and static UI
  lifecycle-action absence

Out of scope:

- `accounts validate`
- `accounts promote`
- `accounts demote`
- `accounts hold`
- `accounts release`
- `accounts retire`
- `accounts onboard`
- desktop app transfer
- runtime core edits
- direct registry/state/log access

## Canon Boundary

`accounts list --json` remains the truth owner for this screen. The browser
does not receive `command_id`, does not submit arbitrary commands, and does not
receive raw account command packets.

The screen is explicitly read-only. Lifecycle affordances are either absent or
disabled/deferred copy.

## Acceptance Evidence

- `/api/accounts-readonly` calls only `accounts_list`.
- `auth_ref`, raw local paths, private account labels, tokens, raw logs, and raw
  command packets are not exposed by the accounts snapshot.
- Invalid accounts packets become `integration_failure`.
- `Overview <-> Accounts` navigation works in the web renderer.
- Fixture and live read-only accounts modes render in browser smoke.
- `runtime.py`, `web_ui.py`, and `ui_shell.py` are not part of this UI contour.
