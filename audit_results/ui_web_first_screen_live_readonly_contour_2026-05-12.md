# UI Web First Screen Live Read-Only Binding

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_LIVE_READONLY_BINDING`

## Goal

Bind the first web-design screen to live read-only Wild Boar Proxy JSON command
packets through the bounded command adapter, while keeping fixture mode available
and keeping all actions disabled.

## Scope

- Add a local web-design live server.
- Serve the existing first-screen static assets.
- Add one read-only endpoint: `/api/live-readonly`.
- Call only approved read-only adapter command IDs.
- Map successful command packets into the existing overview visual shape.
- Map command errors, packet mismatches, and integration errors to explicit
  `integration_failure`.

## Out Of Scope

- Runtime-core edits.
- `web_ui.py` / `ui_shell.py` rewrites.
- Action buttons and mutations.
- Desktop shell work.
- Additional screens.
- Direct runtime/state/log file reads.

## Required Read Commands

- `status`
- `healthcheck`
- `mode_get`
- `accounts_list`
- `rollout_rotation_inspect`

If any required read command fails, the live snapshot must not render stale green.
