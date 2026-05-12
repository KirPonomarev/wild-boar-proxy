# UI Web Refresh And Diagnostics Actions

Date: 2026-05-12

Contour ID: `UI_WEB_REFRESH_AND_DIAGNOSTICS_ACTIONS`

## Goal

Add the first safe actions to the first web overview without enabling mutating
runtime controls.

## Allowed Actions

- `refresh_health_detail` -> `healthcheck`
- `export_diagnostics` -> `diagnostics_export`
- `stable_repair_plan` -> `stable_repair_dry_run`

## Boundary

- Browser submits `ui_action`, never adapter `command_id`.
- Server maps `ui_action` to adapter command internally.
- Diagnostics remains a support artifact.
- Stable repair dry-run remains recovery planning.
- Healthcheck remains runtime detail evidence.
- Action results never overwrite primary overview truth.
- Sync, mode set, smoke, launch client, repair apply, and account mutations stay
  unreachable.
