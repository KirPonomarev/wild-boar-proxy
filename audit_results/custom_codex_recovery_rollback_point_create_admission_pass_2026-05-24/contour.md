# CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS

## Contour Capsule

- contour: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS`
- date: `2026-05-24`
- branch: `codex/external-agent-lab-isolated`
- base_head: `15c00441`
- scope: define a machine-checked admission packet for future rollback-point creation
- explicit non-goal: no rollback point creation, no snapshot file creation, no rollback apply, no process kill, no arbitrary path cleanup, no credential mutation, no current/Original Codex touch
- result token: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_READY`
- next contour: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_PASS`

## Canon Boundaries

- WBP remains the control layer.
- Browser remains a renderer and check trigger only.
- JSON packets remain primary truth.
- `CLIProxyAPI` remains the engine and is not changed in this contour.
- Current Codex home/process and Original Codex profile remain forbidden surfaces.
- `CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS` is not claimed.

## Implementation Surface

- `wild_boar_proxy/codex_recovery_contract.py`
  - Adds `build_custom_recovery_rollback_point_create_admission_packet`.
  - Adds structural validation for the rollback-point dry-run upstream packet.
  - Adds admission checks for allowed future write surfaces.
- `wild_boar_proxy/web_design_live_server.py`
  - Adds GET-only `/api/codex/custom/recovery/rollback-point-create-admission`.
- `wild_boar_proxy/web_design_ui/index.html`
  - Adds a minimal admission status row, button, and pending packet.
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - Adds refresh/render support for the admission packet.
- Tests cover contract semantics, live endpoint POST rejection, forbidden browser fields, forbidden surfaces, and UI no-POST/no-dangerous-action guards.

## Success Criteria

- `rollback_point_dry_run_contract_valid=true`.
- `rollback_point_create_admission_defined=true`.
- `rollback_point_create_admitted=true` only with `rollback_point_create_admitted_scope=next_contour_only`.
- `rollback_point_create_admitted_for_current_contour=false`.
- `rollback_point_create_performed=false`.
- `rollback_point_created=false`.
- `snapshot_file_created=false`.
- `filesystem_write_performed=false`.
- `write_surface_machine_check_performed=true`.
- `write_surfaces_all_eligible=true`.
- `rollback_apply_admitted=false`.
- `rollback_live_ready=false`.
- `recovery_operator_ready=false`.
- `current_codex_touched=false`.
- `original_codex_touched=false`.
- Browser payload remains forbidden.
- Dangerous recovery actions remain disabled.

## Resume From Here

If this contour is accepted, resume at `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_LIVE_PASS`.
That next contour may create a rollback point only after revalidating this admission packet and declaring concrete write behavior.
