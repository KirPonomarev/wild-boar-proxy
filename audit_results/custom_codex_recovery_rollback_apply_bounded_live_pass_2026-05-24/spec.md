# Spec

## Endpoint

`POST /api/codex/custom/recovery/rollback-apply`

Expected request body:

```json
{}
```

## Success Packet

Required truth:

- `status=ok`
- `machine_error_code=ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED`
- `claim_scope=custom_codex_recovery_rollback_apply_bounded_live_only`
- `rollback_apply_bounded_live_performed=true`
- `rollback_apply_performed=true`
- `rollback_apply_completed_scope=bounded_apply_receipt_only`
- `rollback_completed=true`
- `filesystem_read_performed=true`
- `filesystem_read_scope=owned_generated_recovery_artifact`
- `filesystem_write_performed=true`
- `filesystem_write_scope=owned_generated_recovery_artifact`
- `rollback_live_ready=false`
- `recovery_operator_ready=false`
- `process_kill_performed=false`
- `current_codex_touched=false`
- `original_codex_touched=false`
- `current_codex_home_touched=false`
- `auth_material_touched=false`
- `secret_value_recorded=false`

## Write Surface

The success path writes exactly one receipt artifact:

```text
custom_codex_recovery_rollback_apply_receipt
```

No receipt manifest or auxiliary apply-state file is written in this contour.

## Browser Rejection

Browser payload fields are rejected before read/write:

- target/path fields
- backend/route fields
- session/process fields
- HOME/CODEX_HOME fields
- auth/token/key/secret fields

Blocked packet requirements:

- `status=blocked`
- `machine_error_code=ROLLBACK_APPLY_BROWSER_FIELD_REJECTED`
- `filesystem_read_performed=false`
- `filesystem_write_performed=false`
- `rollback_apply_performed=false`

## Canon Boundary

This contour does not claim full rollback restore or `CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS`.
