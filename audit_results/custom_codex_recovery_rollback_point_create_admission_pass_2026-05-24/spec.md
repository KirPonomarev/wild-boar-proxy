# Spec: Codex Custom Rollback Point Create Admission

## Objective

Add a GET-only, server-issued admission contract that determines whether future rollback-point creation can be admitted in the next contour. This contour does not create rollback points, snapshots, or rollback state files.

## In Scope

- `GET /api/codex/custom/recovery/rollback-point-create-admission`
- Structural validation of `/api/codex/custom/recovery/rollback-point-dry-run`
- Machine checks for future write surface eligibility
- Minimal web UI row/button/packet rendering
- Tests, browser proof, independent audit, closeout

## Out of Scope

- `POST /api/codex/custom/recovery/rollback-point-create-admission`
- `POST /api/codex/custom/recovery/rollback-point`
- `POST /api/codex/custom/recovery/snapshot`
- `POST /api/codex/custom/recovery/rollback`
- `POST /api/codex/custom/recovery/apply`
- `POST /api/codex/custom/recovery/kill`
- `POST /api/codex/custom/recovery/cleanup-path`
- Rollback point file creation
- Snapshot file creation
- Rollback apply
- Process kill
- Current Codex or Original Codex mutation

## Allowed Future Write Surfaces

- `owned_temp_session_root`
- `owned_wbp_runtime_state`
- `owned_generated_recovery_artifact`

Each surface is checked as future eligibility metadata only. `filesystem_write_performed=false` and `write_admitted_for_current_contour=false` are mandatory.

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

## Acceptance Criteria

- [x] GET endpoint returns a machine packet.
- [x] POST recovery admission/create/apply/kill paths remain 404.
- [x] Shallow upstream dry-run packets fail closed.
- [x] Forbidden or unknown write surfaces fail closed.
- [x] Browser supplies no target/path payload.
- [x] No filesystem write or snapshot creation occurs.
- [x] No rollback apply, process kill, or operator-ready claim is made.

## Verification

- tests: bundled Python unit tests
- build: `node --check`
- manual: browser proof on local server
- live evidence: local server only, no live rollback or filesystem write
