<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS_REOPEN Spec

## Goal

Connect the web `onboard_account` action to the owner-owned sandbox login
admission surface, without browser-side secrets, paths, tokens, auth references,
or backend-id selection.

## Canon

Decision order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Flow

The admitted sandbox web flow is:

1. web sends only `{ "ui_action": "onboard_account" }`
2. server runs `accounts login start --provider sandbox --json`
3. server runs `accounts login complete --session <id> --state <state> --proof sandbox-ok --json`
4. owner layer materializes sandbox-only synthetic auth
5. server runs `accounts onboard --json --auth-ref <server-owned-auth-ref>`
6. web performs accounts-readonly refresh
7. reserve account appears from refresh proof

## Boundaries

In scope:

- owner sandbox login bridge from web action
- internal-only adapter commands for login start, login complete, and auth-ref onboarding
- sandbox-only auth materialization
- reserve-first proof and accounts-readonly refresh
- action response redaction for raw auth paths

Out of scope:

- real provider OAuth
- desktop app migration
- API route create/adopt
- browser token/password/file/path inputs
- promotion to `active`
- packaging or redesign

## Success

Closed only if browser click proof shows:

- modal is live owner login bridge, not dry-run loop
- confirm dispatches `onboard_account`
- login bridge completes
- onboarding returns `explicit_auth_imported_to_reserve`
- `reserve_first_proven=true`
- refreshed accounts contain selected backend in `reserve`
- action response does not expose raw sandbox auth path
