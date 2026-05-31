# CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS

## Contour Capsule

- contour: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS`
- date: `2026-05-24`
- branch: `codex/external-agent-lab-isolated`
- base_head: `157ba1b6`
- scope: define a machine-readable rollback-point dry-run contract for Codex Custom recovery
- explicit non-goal: no rollback-point creation, snapshot file creation, rollback apply, process kill, arbitrary path cleanup, credential mutation, or Original/current Codex touch
- next contour: `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS`

## Canon Boundaries

- WBP remains the control layer.
- Browser remains a renderer and refresh trigger only.
- JSON packets remain primary truth.
- `CLIProxyAPI` remains the engine and is not changed in this contour.
- Current Codex home/process and Original Codex profile are forbidden surfaces.
- `CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS` is not claimed.

## Implementation Surface

- `wild_boar_proxy/codex_recovery_contract.py`
  - Adds `build_custom_recovery_rollback_point_dry_run_packet`.
  - Extends forbidden browser fields with `snapshot_path` and `rollback_target`.
- `wild_boar_proxy/web_design_live_server.py`
  - Adds GET-only `/api/codex/custom/recovery/rollback-point-dry-run`.
- `wild_boar_proxy/web_design_ui/index.html`
  - Adds a dry-run-only status row, button, and pending packet.
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - Adds refresh/render support for the dry-run packet.
- Tests cover contract semantics, live endpoint POST rejection, and UI guardrails.

## Success Criteria

- `rollback_point_contract_defined=true` only after the rollback process-owner dry-run contract is OK.
- `rollback_point_present=false`.
- `rollback_point_create_admitted=false`.
- `rollback_apply_admitted=false`.
- `rollback_live_ready=false`.
- `rollback_write_surfaces_contract_defined=true`.
- `rollback_write_surfaces_machine_checked=false`.
- `rollback_write_surfaces_dry_run_checked=true`.
- `rollback_verification_packet_defined=true`.
- `recovery_operator_ready=false`.
- `filesystem_write_performed=false`.
- `snapshot_file_created=false`.
- `current_codex_touched=false`.
- `original_codex_touched=false`.
- Browser payload remains forbidden.
- Dangerous recovery actions remain disabled.

## Resume From Here

If this contour is accepted, resume at `CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_CREATE_ADMISSION_PASS`.
That next contour must define write-surface machine checks before admitting any rollback-point creation.
