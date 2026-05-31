<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# OWNER_PROVIDER_LOGIN_CALLBACK_PASS Spec

## Goal

Implement a real owner-owned provider login/callback path for web account
connection without browser-side secret, token, path, auth-ref, or backend-id
intake.

## Canon

Decision order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Required Flow

The desired product flow is:

1. web sends only `ui_action=onboard_account`
2. owner starts a real provider login session
3. browser opens owner/provider login URL
4. provider callback is handled by owner/engine layer
5. owner materializes auth under sandbox-only runtime paths
6. owner returns strict JSON result
7. `accounts onboard --json --auth-ref <owner-ref>` imports backend to `reserve`
8. web shows success only after accounts-readonly refresh proof

## STOP Finding

This contour cannot be honestly implemented from the current codebase state.

Verified blocker:

- `accounts login start` accepts arbitrary `--provider`, but runtime supports
  only `sandbox`.
- unsupported real provider example `codex` returns
  `LOGIN_PROVIDER_UNSUPPORTED`.
- there is no `accounts login status` command.
- there is no owner callback/listener route for provider completion.
- `COMMAND_API.md` only specifies the sandbox login owner surface.

## Verdict

`STOP_AND_DIAGNOSE`.

The next practical contour must be:

`OWNER_PROVIDER_AUTH_ADMISSION_PASS`

Its job is to define and implement the first real provider owner surface:

- provider choice
- login start URL semantics
- callback/listener ownership
- state/nonce/PKCE policy when applicable
- sandbox-only auth materialization
- strict JSON result
- no browser secret/path/token intake

Only after that should `OWNER_PROVIDER_LOGIN_CALLBACK_PASS` reopen.
