<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: External Models C4 UI Binding

## Objective

Define the future `external-models` UI as a strict consumer of existing command
packets without introducing UI implementation, new truth surfaces, or command
semantic drift.

This contour exists to prepare a canon-safe UI contract while the design gate
remains unearned.

## In Scope

- packet-to-screen mapping for:
  - `external-models status --json`
  - `external-models models --json`
  - `external-models routes list --json`
  - `external-models routes validate --json --route <id>`
  - `external-models check --json --route <id>`
  - `external-models profile codex-desktop --json --route <id>`
  - `external-models evidence capture --json --route <id>`
- UI action matrix covering:
  - read actions
  - route mutations
  - explicit network actions
  - confirmation rules
  - post-action refresh rules
- rendering rules for:
  - synthetic lifecycle truth
  - route-provider-only validation truth
  - failure states
  - support/evidence states
- redacted fixture packets derived from real C1-C3 command outputs
- explicit non-go rules for runtime/listener/profile/Codex readiness inference

## Out of Scope

- any UI code
- any web, desktop, or shell UI component
- any design system work or visual polish
- any installer or packaging work
- any command-surface expansion
- any command semantic change for UI convenience
- any direct `routes.json`, `state.json`, log, or evidence-file parsing as UI truth
- any automatic `validate` / `check` polling behavior

## Constraints

- `AGENTS.md` blocks rich UI expansion until
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.
- `UI_READINESS_SPEC.md` is a readiness/spec boundary only.
- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- The UI must consume command packets as primary truth.
- `external-models status --json` remains synthetic lifecycle truth only.
- `routes validate` and `check` remain `route_provider_only` truth.
- `verified` means provider compatibility evidence only, never runtime readiness.

## Assumptions

- C1, C2, and C3 are closed and pushed.
- The future UI will be allowed only after the broader design gate is earned.
- Existing command packets are sufficiently stable to become the first UI
  contract.

## Packet Surface

### Common envelope

All `external-models` UI-consumed commands use the canonical top-level fields:

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`
- `liveness`
- `severity`
- `operator_action`
- `data`
- `timestamp_utc`

### Command mapping

#### `external-models status --json`

Primary purpose:
- synthetic lifecycle overview

Required `data` fields:
- `foundation_phase`
- `adapter_runtime_available`
- `lifecycle_mode`
- `adapter_state`
- `listener_proven`
- `runtime_claim_blocked`
- `profile_ready`
- `routes_count`
- `observed_routes_count`
- `adapter`
- `local_auth`

Forbidden UI inference:
- listener is available
- runtime is healthy
- profile is ready

#### `external-models models --json`

Primary purpose:
- route registry projection for operator browsing

Required `data` fields:
- `models`
- `count`
- `source`
- `listener_proven`
- `runtime_claim_blocked`

Required per-model fields:
- `route_id`
- `display_name`
- `provider`
- `base_url`
- `endpoint_path`
- `upstream_model`
- `compatibility`
- `cost_class`
- `enabled`
- `lane_role`
- `fallback_eligible`
- `synthetic_adapter_state`
- `profile_ready`

Forbidden UI inference:
- route availability
- live provider status
- runtime readiness

#### `external-models routes list --json`

Primary purpose:
- declarative route inspection

Required `data` fields:
- `routes`
- `count`

Each route is declarative config only and may include:
- `schema_version`
- `route_id`
- `display_name`
- `provider`
- `base_url`
- `endpoint_path`
- `upstream_model`
- `compatibility`
- `auth`
- `cost_class`
- `lane_role`
- `fallback_eligible`
- `enabled`

Forbidden UI inference:
- auth validity
- provider reachability
- route readiness

#### `external-models routes validate --json --route <id>`

Primary purpose:
- route-provider validation evidence

Required `data` fields on success:
- `validation_kind`
- `network_dependent`
- `listener_proven`
- `runtime_claim_blocked`
- `profile_ready`
- `verification_scope`
- `route_state`
- `requested_model`
- `effective_model`
- `provider`
- `evidence_path`
- `available_models_count`
- `latency_ms`

Required `data` fields on error:
- `validation_kind`
- `network_dependent`
- `listener_proven`
- `runtime_claim_blocked`
- `profile_ready`
- `verification_scope`
- `route_state`
- `requested_model`
- `provider`

Required rendering note:
- `verification_scope=route_provider_only`

Forbidden UI inference:
- runtime ready
- listener ready
- profile ready
- Codex ready

#### `external-models check --json --route <id>`

Primary purpose:
- bounded route-provider smoke evidence

Required `data` fields on success:
- `check_kind`
- `network_dependent`
- `listener_proven`
- `runtime_claim_blocked`
- `profile_ready`
- `verification_scope`
- `route_state`
- `requested_model`
- `effective_model`
- `provider`
- `fallback_used`
- `fallback_chain`
- `evidence_path`
- `latency_ms`
- `request_count`

Required `data` fields on error:
- `check_kind`
- `network_dependent`
- `listener_proven`
- `runtime_claim_blocked`
- `profile_ready`
- `verification_scope`
- `route_state`
- `requested_model`
- `provider`
- `fallback_used`
- `fallback_chain`

Required rendering note:
- `verification_scope=route_provider_only`

Forbidden UI inference:
- runtime ready
- listener ready
- profile ready
- Codex ready

#### `external-models profile codex-desktop --json --route <id>`

Primary purpose:
- non-mutating profile packet preview

Required `data` fields:
- `profile_kind`
- `route_id`
- `base_url`
- `model`
- `api_key_source`
- `writes_external_config`
- `profile_ready`
- `listener_proven`
- `runtime_claim_blocked`
- `synthetic_endpoint_contract`
- `prerequisite`

Forbidden UI inference:
- Codex can connect now
- listener exists
- route is ready for traffic

#### `external-models evidence capture --json --route <id>`

Primary purpose:
- local support artifact capture

Required `data` fields:
- `route_id`
- `network_dependent_evidence`
- `evidence_path`

Forbidden UI inference:
- provider compatibility proven
- runtime proven

## Future Screen Contract

### External Models Overview

Uses:
- `status`
- `models`

May display:
- synthetic adapter state
- route count
- observed route count
- local token presence

Must explicitly show:
- `listener_proven=false`
- `runtime_claim_blocked=true`
- `profile_ready=false`

### Route Registry

Uses:
- `routes list`
- `models`

May display:
- declarative route config
- projected model identity
- enabled/disabled state
- cost class

Must not synthesize:
- provider status
- runtime status

### Route Validation Panel

Uses:
- `routes validate`
- `check`

Must display:
- success/error packet
- `verification_scope`
- route-local state
- latency when present
- fallback truth from `check`
- evidence path when present

Must explicitly label:
- provider evidence only
- not runtime evidence

### Codex Profile Panel

Uses:
- `profile codex-desktop`

Must display:
- non-mutating profile packet only
- `writes_external_config=false`
- `profile_ready=false`
- prerequisite string

### Evidence / Support Panel

Uses:
- `evidence capture`
- previously returned evidence paths as support references only

Must distinguish:
- local evidence
- network-dependent provider evidence

Must not label evidence as readiness proof.

## Action Matrix

### Safe read actions

- refresh status
- refresh routes
- refresh models
- view profile packet
- view validate result
- view check result
- view evidence result

No confirmation required.

### Mutating actions

- `external-models routes enable --json --route <id>`
- `external-models routes disable --json --route <id>`

Confirmation required.

### Explicit network actions

- `external-models routes validate --json --route <id>`
- `external-models check --json --route <id>`
- `external-models evidence capture --json --route <id>`

Rules:
- explicit operator action only
- never auto-run on page load
- never background-polled in UI v1
- never converted into a global green readiness badge

## Refresh Rules

After:
- route enable
- route disable
- validate
- check

Required refresh order:

1. `external-models routes list --json`
2. `external-models models --json`
3. `external-models status --json`

Optional route-specific refresh:

- `external-models profile codex-desktop --json --route <id>`

No local file reads are permitted for truth refresh.

## Failure Rendering Rules

Future UI must render these as distinct states:

- `provider_auth_failed`
- `provider_network_failed`
- `model_not_available`
- `paid_route_blocked`
- `invalid_upstream_response`
- `limited`
- `blocked`

The UI must not collapse these into generic:
- offline
- healthy
- ready
- unsupported

## Fixture Provenance

Derived fixtures live in:

- `audit_results/external_models_c4_fixture_packets_2026-05-12.json`

They are derived from real isolated command executions using:
- isolated `WBP_*` paths
- loopback mock providers for `validate` and `check`
- redacted temp paths, evidence paths, timestamps, and loopback ports

## Acceptance Criteria

- [ ] a C4 spec exists for future external-models UI consumption
- [ ] every intended screen is mapped to existing command packets
- [ ] every intended action is mapped to existing commands
- [ ] runtime truth and route-provider truth are explicitly separated
- [ ] fixture packets are derived from real C1-C3 outputs
- [ ] no UI code is introduced
- [ ] no command semantics are changed for UI convenience
- [ ] no direct file/log parsing is authorized as UI truth
- [ ] no auto-validation or background validation polling is authorized in v1
- [ ] closeout explicitly states that UI implementation remains gated

## Verification

- tests:
  - `python3 -m unittest -q tests.test_external_models`
  - `python3 -m unittest -q tests.test_cli_external_models`
  - `python3 -m unittest -q tests.test_external_agent_lab`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
- manual:
  - generate isolated real command outputs for all C4 fixture commands
  - verify fixture provenance and redaction scope
  - scope-check that no UI code was touched
- live evidence:
  - none

## Open Questions

- Whether future UI v1 should expose separate route-local observed state cards or
  derive them only from the most recent validate/check packet
- Whether future UI should show raw `auth.secret_ref` in the declarative route
  list or suppress it in presentation while preserving packet truth underneath
