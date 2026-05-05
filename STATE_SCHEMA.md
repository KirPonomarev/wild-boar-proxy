<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

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

Current execution-wave meaning:

- `active_min` is the lower policy floor for the managed active pool
- `active_target` is the current staged active-pool ceiling for promotion truth
- `reserve_target` is the minimum reserve floor that promotion must preserve

Canonical staged policy mapping for the current contour:

- stage `10` sets `active_min = 10`, `active_target = 10`, `reserve_target = 0`
- stage `15` sets `active_min = 15`, `active_target = 15`, `reserve_target = 0`
- stage `20` sets `active_min = 20`, `active_target = 20`, `reserve_target = 0`

Stage selection updates policy truth only.
It does not itself promote or demote any backend, and it does not prove stage
completion by itself.

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

If `current_proxy_url` is materialized, it is:

- current live control-layer outbound proxy truth
- separate from `last_known_good_proxy_url`
- separate from nested `proxy_reprobe.working_candidate`
- effectful only through a repo-owned activation surface, not by ambient shell
  proxy env alone
- not historical truth by itself
- not final runtime truth without live checks by itself

Optional fields currently supported by the local contour:

- `active_count`
- `reserve_count`
- `retired_count`
- `healthy_count`
- `degraded_count`
- `down_count`
- `selected_backend_ids_observed_at`
- `probe_port`
- `last_proxy_discovery_at`
- `last_full_deep_probe_at`
- `last_known_good_proxy_url`
- `last_known_good_proxy_observed_at`
- `stable_runtime_consumer_snapshot`
- `selected_backend_snapshot`

`selected_backend_ids` is a supervisor/runtime snapshot field.
It is not registry lifecycle truth and must not be inferred from active registry
ids or active registry counts.

If `selected_backend_ids_observed_at` is present, it records when the selected
backend snapshot was observed.
Consumers may use it for freshness classification, but cached freshness does
not override live runtime checks.

If `selected_backend_snapshot` is materialized, it is:

- cached bounded local participation evidence
- a read/validation contract for rollout evidence surfaces
- separate from registry lifecycle truth
- separate from active-pool counts
- not final runtime truth without live checks
- not a production writer contract in the current contour
- not sufficient by itself for `STABLE_20_PROVED`, `SCALE_COMPLETE`, or
  `PILOT_READY`

Required fields if materialized:

- `schema_version`
- `snapshot_kind`
- `source_class`
- `source_name`
- `source_run_id`
- `producer_version`
- `observed_at_utc`
- `selected_backend_ids`
- `selected_backends_digest`
- `claim_scope`

Supported `schema_version`:

- `1`

Supported `snapshot_kind`:

- `selected_backend_participation`

Supported `claim_scope`:

- `bounded_local_participation_evidence_only`

Supported `source_class` values:

- `engine_observed`
- `runtime_observed`
- `supervisor_owner_observed`
- `external_owner_path_observed`

`selected_backends_digest` is the SHA-256 digest of the normalized selected
backend id list.
The normalized list is sorted, string-only, and encoded as compact JSON before
hashing.

Migration rule:

- v1 nested `selected_backend_snapshot` is optional.
- existing flat `selected_backend_ids` plus `selected_backend_ids_observed_at`
  remains legacy-compatible read input.
- no migration may synthesize selected ids from registry active ids, registry
  active counts, routing candidates, or pool policy.
- invalid nested snapshots must be surfaced as invalid and must not be masked by
  legacy flat fallback.

If `last_known_good_proxy_url` and `last_known_good_proxy_observed_at` are
materialized, they are:

- control-layer runtime-state history
- bounded reprobe input only
- separate from `current_proxy_url`
- not final runtime truth without live checks
- not by themselves sufficient to change live `status`, `liveness`,
  `machine_error_code`, `endpoint`, or `current_proxy_url`

If `stable_runtime_consumer_snapshot` is materialized, it is:

- runtime-state snapshot evidence
- not lifecycle registry truth
- not final runtime truth without live checks
- not control-layer target truth

Required fields if materialized:

- `schema_version`
- `activation_method`
- `selected_config_file`
- `selected_source_kind`
- `selected_source_path`
- `activation_outcome`
- `fallback_reason`
- `observed_at_utc`

Current canonical `activation_outcome` values:

- `approved_target_activated`
- `observed_source_selected`
- `observed_source_fallback`

Deterministic stable recovery may refresh this same snapshot topic through the
serialized runtime-state mutation path.
The current recovery owner path in `healthcheck --json` reuses this snapshot
surface and does not require a separate persisted recovery snapshot by default.
`stable_service_disabled` entry-lane classification remains command-packet truth
by default and does not widen this snapshot schema or introduce a separate
persisted recovery metadata file.

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

`stable repair --dry-run --json` and `stable repair --apply --json` do not
introduce a new persisted repair metadata file in this contour.

Its repair authority and target reconciliation contract remain command-packet
surfaces, while repair apply mutates only the approved control-owned target
inventory entries:

- `stable-repair-target/codex-*.json`

The apply transaction may create ephemeral sibling scratch directories under
`managed/`:

- `.stable-repair-stage-*`
- `.stable-repair-backup-*`

These are process-local transaction mechanics only. They are not persisted
state surfaces and must not remain after success or rollback.

`stable-runtime-config.generated.yaml` is a control-owned generated stable
runtime config artifact.

It is:

- engine-facing derived config
- companion-managed data
- not registry state
- not runtime truth state
- not diagnostics state

It may remain absent until a serialized stable-runtime consumer activation or
deterministic recovery path materializes it inside the current bounded launcher
seam.

The generated config is handed to activation only through the narrow
launcher-scoped `WBP_STABLE_CONFIG` override contract.
That handoff must not become a generic config-routing surface.
Deterministic stable recovery must regenerate this artifact per approved-target
attempt rather than treating a stale artifact as authoritative truth.

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
- `stable-runtime-config.generated.yaml` may be mutated only by the serialized
  stable-runtime consumer activation path

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
