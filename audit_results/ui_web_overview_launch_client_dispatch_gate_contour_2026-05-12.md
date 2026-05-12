# UI Web Overview Launch Client Dispatch Gate Contour

Date: 2026-05-12

Contour ID: `UI_WEB_OVERVIEW_LAUNCH_CLIENT_DISPATCH_GATE`

## Goal

Prepare the first web overview screen for `Launch Client` as bounded
host-client dispatch, without making dispatch runtime truth and without adding
file picking, client discovery, config mutation, installer work, or desktop
transfer.

## Scope

In scope:

- `launch_client_dispatch` UI action
- server-owned bounded `client_path`
- launch availability metadata
- confirmation before dispatch
- post-action live overview refresh
- dispatch-only claim scope

Out of scope:

- browser-provided `client_path`
- browser-provided `command_id`
- file picker
- auto-discovery
- config writes
- desktop transfer
- installer/package work
- host-client session success claims

## Canon Boundary

Browser sends only `ui_action`.

The live server may attach structured `client_path` internally only when a
server-owned bounded path is provided. `/api/actions` must not expose
`adapter_command_id` or private paths.

Runtime truth remains owned by `/api/live-readonly` and strict JSON command
surfaces.
