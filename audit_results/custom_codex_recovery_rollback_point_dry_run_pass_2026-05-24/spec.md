# Spec: Codex Custom Recovery Rollback Point Dry-Run

## Purpose

Define a narrow control-layer contract that describes what a future rollback point would require, without creating any file, accepting any browser-supplied target, applying rollback, killing a process, or claiming operator readiness.

## Endpoint

`GET /api/codex/custom/recovery/rollback-point-dry-run`

No POST endpoint is admitted in this contour.

## Required Packet Fields

- `claim_scope="custom_codex_recovery_rollback_point_dry_run_only"`
- `machine_error_code="ROLLBACK_POINT_DRY_RUN_CONTRACT"` when upstream process-owner dry-run contract is OK
- `rollback_point_contract_defined=true`
- `rollback_point_present=false`
- `rollback_point_create_admitted=false`
- `rollback_apply_admitted=false`
- `rollback_live_ready=false`
- `rollback_write_surfaces_contract_defined=true`
- `rollback_write_surfaces_machine_checked=false`
- `rollback_write_surfaces_dry_run_checked=true`
- `rollback_verification_packet_defined=true`
- `rollback_verification_packet_present=false`
- `recovery_operator_ready=false`
- `filesystem_write_performed=false`
- `snapshot_file_created=false`
- `current_codex_touched=false`
- `original_codex_touched=false`
- `browser_payload_allowed=false`
- `dangerous_actions_disabled=true`

## Metadata-Only Allowed Surfaces

- `owned_temp_session_root`
- `owned_wbp_runtime_state`
- `owned_generated_recovery_artifact`

These are contract metadata only in this contour; `filesystem_write_admitted=false` and `machine_checked=false`.

## Forbidden Surfaces

- `current_codex_home`
- `current_codex_process`
- `original_codex_profile`
- `host_codex_profile`
- `arbitrary_path`
- `auth_material`
- `token_store`
- `secret_file`
- `global_runtime_reset`
- `external_account_state`
- `external_api_route_secret`

## Forbidden Browser Fields

- `backend_id`
- `route_id`
- `path`
- `snapshot_path`
- `rollback_target`
- `pid`
- `process_id`
- `token`
- `auth`
- `api_key`
- `secret`
- `CODEX_HOME`
- `HOME`

## Out Of Scope

- `POST /api/codex/custom/recovery/rollback-point`
- `POST /api/codex/custom/recovery/snapshot`
- `POST /api/codex/custom/recovery/rollback`
- `POST /api/codex/custom/recovery/apply`
- `POST /api/codex/custom/recovery/cleanup-path`
- `POST /api/codex/custom/recovery/kill`
- Desktop GUI, installer, account mutation, external route mutation, or production/operator-ready claims.
