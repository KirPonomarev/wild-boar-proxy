# State Schema

## Schema policy

- every JSON state file must include `schema_version`
- required fields and optional fields must be declared explicitly
- each schema change must define a migration expectation before use
- registry and runtime state use a single-writer mutation model
- concurrent mutators are forbidden
- all writes must be atomic
- partial writes are invalid state, not recoverable success
- schema must support 20 accounts without format redesign

## Registry

`backend-registry.json` is the lifecycle source of truth.

Required top-level fields:

- `schema_version`
- `version`
- `updated_at`
- `stable_default_backend_id`
- `pool_policy`
- `backends`

Required `pool_policy` fields:

- `active_min`
- `active_target`
- `reserve_target`

Required backend fields:

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

Optional backend fields currently supported by the local contour:

- `added_at`
- `disabled_reason`
- `drain_until`
- `enabled`
- `half_open_since`
- `last_deep_probe_at`
- `last_error_class`
- `last_probe_at`
- `last_probe_level`
- `last_transition_at`
- `priority`
- `proxy_mode`
- `type`

Lifecycle values stored in `pool`:

- `reserve`
- `active`
- `retired`

`manual_hold` is a required registry field.
Transition and routing semantics for hold are defined in `STATE_TRANSITIONS.md`.

## Runtime state

`supervisor-state.json` is a snapshot, not the final truth without live checks.

Required fields:

- `schema_version`
- `version`
- `status`
- `effective_mode`
- `last_sync_at`
- `last_error`
- `selected_backend_ids`
- `managed_port`
- `current_proxy_url`
- `stable_default_backend_id`

Optional fields currently supported by the local contour:

- `active_count`
- `reserve_count`
- `retired_count`
- `healthy_count`
- `degraded_count`
- `down_count`
- `probe_port`
- `last_proxy_discovery_at`
- `last_full_deep_probe_at`

## Mode files

- `runtime-mode.txt` stores desired mode
- `runtime-effective-mode.txt` stores actual mode after preflight

## Control metadata

`approved-repair-target.json` is the control-layer truth surface for the
approved repair-target reference.

It is not:

- lifecycle registry truth
- runtime health truth
- supervisor runtime state
- effective-mode truth

Required fields once materialized:

- `schema_version`
- `target_identity`
- `target_kind`
- `inventory_dir`
- `ownership`
- `location_scope`

`target-switch-transaction.json` is the control-layer transaction metadata
surface for the serialized target-switch apply path.

Required fields once materialized:

- `schema_version`
- `transaction_status`
- `target_identity`
- `target_kind`
- `inventory_dir`
- `reference_file`
- `ownership`
- `location_scope`

The target-switch apply path may also materialize the approved empty inventory
directory:

- `stable-repair-target/`

That directory may remain empty of `codex-*.json` auth files until a later
repair contour opens inventory-population behavior.

## Write-surface ownership

- `backend-registry.json` may be mutated only by the serialized account-state
  mutation path
- `supervisor-state.json` may be mutated only by the serialized runtime-state
  mutation path
- `runtime-mode.txt` may be mutated only by the mode-selection path
- `runtime-effective-mode.txt` may be mutated only by successful live
  preflight, fallback, or recovery completion
- `approved-repair-target.json` may be mutated only by the serialized
  target-switch selection path
- `target-switch-transaction.json` may be mutated only by the serialized
  target-switch transaction path

Every mutating path must declare which of these surfaces it writes before the
write begins.

## Persistence rules

- atomic write means write to a sibling temp file, verify, and replace in one
  committed switch
- the switch step may not expose partially written JSON or mixed old and new
  state
- UI must distinguish `healthy`, `down`, `stale`, and `unknown`

## Mutation rules

- any operation that changes active routing, registry lifecycle, hold state,
  runtime mode, or managed runtime state must go through one serialized writer
- a mutator may not infer current truth from cache alone when live state is
  required by contract
- runtime snapshot updates may not overwrite registry lifecycle truth

## Migration expectation

Schema migration and legacy import must use one transaction model:

1. snapshot
2. stage
3. verify
4. switch
5. rollback

No migration is considered successful if old and new state are partially mixed.
