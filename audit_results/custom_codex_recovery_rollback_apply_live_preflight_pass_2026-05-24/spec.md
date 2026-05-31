# Spec

## Endpoint

`GET /api/codex/custom/recovery/rollback-apply/live-preflight`

The endpoint composes the existing rollback-apply admission dry-run and returns a JSON packet.

## Success Packet Requirements

- `status=ok`
- `machine_error_code=ROLLBACK_APPLY_LIVE_PREFLIGHT_EVALUATED`
- `claim_scope=custom_codex_recovery_rollback_apply_live_preflight_only`
- `rollback_apply_live_preflight_result=eligible_for_bounded_apply_contour`
- `rollback_apply_dry_run_eligible=true`
- `rollback_point_verified=true`
- `future_write_surfaces_declared=true`
- `future_write_surfaces_all_owned=true`
- `current_codex_excluded=true`
- `original_codex_excluded=true`
- `auth_material_excluded=true`
- `rollback_apply_admitted=false`
- `rollback_apply_ready=false`
- `rollback_apply_performed=false`
- `rollback_completed=false`
- `rollback_live_ready=false`
- `filesystem_write_performed=false`
- `process_kill_performed=false`
- `recovery_operator_ready=false`

The packet truthfully reports upstream server-owned read evidence:

- `source_filesystem_read_performed=true`
- `filesystem_read_performed=true`
- `filesystem_read_scope=owned_generated_recovery_artifact`

## Browser Payload Rejection

Browser-supplied target/path/backend/auth fields are rejected before any read/write:

- `status=blocked`
- `machine_error_code=ROLLBACK_APPLY_LIVE_PREFLIGHT_BROWSER_FIELD_REJECTED`
- `source_filesystem_read_performed=false`
- `filesystem_read_performed=false`
- `filesystem_write_performed=false`
- `rollback_apply_admitted=false`
- `rollback_apply_performed=false`

## Canon Boundary

This contour does not make `CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS` true. It only opens evidence for a later bounded apply contour.
