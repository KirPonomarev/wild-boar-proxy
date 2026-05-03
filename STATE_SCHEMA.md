# State Schema

## Registry

`backend-registry.json` is the lifecycle source of truth.

Required fields:

- `schema_version`
- `id`
- `label`
- `pool`
- `status`
- `manual_hold`
- `auth_ref`
- `fail_count`
- `success_count`
- `last_success`
- `last_error`
- `cooldown_until`
- `notes`

## Runtime state

`supervisor-state.json` is a snapshot, not the final truth without live checks.

Required fields:

- `schema_version`
- `status`
- `effective_mode`
- `last_sync_at`
- `last_error`
- `selected_backend_ids`
- `managed_port`

## Mode files

- `runtime-mode.txt` stores desired mode
- `runtime-effective-mode.txt` stores actual mode after preflight

## Persistence rules

- all writes must be atomic
- UI must distinguish `healthy`, `down`, and `stale`
- schema must support 20 accounts without format changes
