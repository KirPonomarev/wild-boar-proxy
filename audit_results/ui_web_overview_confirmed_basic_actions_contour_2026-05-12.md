# UI Web Overview Confirmed Basic Actions Contour

Date: 2026-05-12

Contour ID: `UI_WEB_OVERVIEW_CONFIRMED_BASIC_ACTIONS`

## Goal

Enable the smallest confirmed basic action set on the first web overview
screen while preserving strict runtime truth ownership.

## Scope

In scope:

- `sync_runtime`
- `set_mode_stable`
- `set_mode_managed`
- `launch_smoke`
- confirmation for mutating actions
- post-action live overview refresh
- action result panel separate from primary overview truth

Out of scope:

- desktop transfer
- `launch client --json`
- account lifecycle actions
- rollout/stage controls
- stable repair apply
- direct state/log/runtime file reads

## Canon Boundary

Browser sends only `ui_action`.

Server owns:

- `ui_action` allowlist
- action metadata
- adapter command mapping
- mutation/confirmation/post-refresh classification

Runtime truth remains owned by strict JSON command surfaces and refreshed via
`/api/live-readonly`.
