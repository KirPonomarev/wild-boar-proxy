<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Readiness Specification

## Purpose

This document defines the first companion UI readiness boundary for Wild Boar
Proxy.

It is a specification for future UI implementation. It is not UI code, visual
design, installer work, packaging work, runtime hardening, live evidence
capture, or a new truth surface.

The UI must present operator workflows by consuming existing strict JSON command
packets. It must not infer runtime truth from local files, logs, cached UI
state, exit code alone, or narrative operator memory.

## Canonical Boundaries

Wild Boar Proxy is the managing layer. CLIProxyAPI remains the engine.

The UI belongs to the managing layer and may:

- display command packet truth
- trigger existing operator commands
- require confirmation for mutating actions
- open files or folders for operator support
- refresh command-derived status after mutating actions

The UI must not:

- implement OAuth or browser callback handling
- duplicate proxy transport, routing, or balancing behavior
- mutate runtime files directly
- parse logs as an API
- read state files as the primary truth source
- synthesize healthy status from cached UI state
- expose live evidence capture as a normal first-pass UI action
- introduce new command surfaces in this contour

## Primary Truth Commands

The first UI implementation must treat these commands as primary truth
interfaces:

```sh
status --json
healthcheck --json
mode get --json
accounts list --json
rollout rotation inspect --json
```

Rules:

- `stdout` must contain exactly one JSON object.
- invalid JSON is a hard integration failure even when exit code is `0`.
- `stderr` may be shown as a support detail but must not be parsed as truth.
- the UI must not fall back to plain-text command output.
- the UI must not keep a previous green status as current truth after invalid,
  missing, stale, or contradictory command evidence.

## Mutating Operator Commands

The first UI implementation may bind buttons only to existing command surfaces.

| UI action | Command | Confirmation | Post-action refresh | Notes |
| --- | --- | --- | --- | --- |
| Switch Stable | `mode set stable --json` | Required | `status --json` | Desired mode change does not prove effective mode. |
| Switch Managed | `mode set managed --json` | Required | `status --json` | Desired mode change does not prove managed health. |
| Run Managed Sync | `sync --json` | Required | `status --json`, `accounts list --json` | Sync result must not be treated as full runtime proof without status evidence. |
| Launch Client | `launch client --json` | Required | `status --json` | Success means bounded dispatch truth, not full host-client session success. |
| Smoke Test | `launch smoke --json` | Required | `status --json` | Bounded runtime smoke evidence only. |
| Stable Repair Dry Run | `stable repair --dry-run --json` | Not required | `status --json` | Non-mutating recovery planning surface. |
| Stable Repair Apply | `stable repair --apply --json` | Required | `status --json` | Mutates only command-owned stable repair target surfaces. |
| Add Account | `accounts onboard --json` | Required | `accounts list --json`, `status --json` | New account must enter reserve first. |
| Validate Account | `accounts validate <id> --json` | Not required | `accounts list --json` | Does not promote or route. |
| Recheck Account | `accounts validate <id> --json` | Not required | `accounts list --json` | UI label alias for validate; no separate command exists. |
| Promote Account | `accounts promote <id> --json` | Required | `accounts list --json`, `status --json` | Promotion is not scale proof. |
| Demote Account | `accounts demote <id> --json` | Required | `accounts list --json`, `status --json` | Active routing impact must be refreshed. |
| Hold Account | `accounts hold <id> --json` | Required | `accounts list --json`, `status --json` | Hold is an operator lifecycle action. |
| Release Account | `accounts release <id> --json` | Required | `accounts list --json`, `status --json` | Release returns to reserve semantics, not active routing. |
| Retire Account | `accounts retire <id> --json` | Required | `accounts list --json`, `status --json` | Retired backends have no automatic return path or implied reactivation lane. |
| Export Diagnostics Bundle | `diagnostics export --json` | Not required | None required | Support snapshot, not runtime health truth. |

Every mutating command response must be handled through the required response
fields listed below. `changed_files` may be shown as an audit/support signal,
but it is not the UI success source.

## Advanced Or Deferred Command Surfaces

These existing command surfaces are not first-pass primary UI actions unless a
future contour explicitly approves them:

| Surface | Status | Reason |
| --- | --- | --- |
| `policy stage set <10|15|20> --json` | Deferred | Policy mutation belongs to staged rollout operations, not basic UI. |
| `rollout stage prove 10 --json` | Deferred | Stage proof is a rollout gate, not basic UI status. |
| `rollout stage prove 15 --json` | Deferred | Stage proof is a rollout gate, not basic UI status. |
| `rollout stage advance 15 <id> --json` | Deferred | Active pool growth requires a staged rollout contour. |
| `rollout stage advance 20 <id> --json` | Deferred | Active pool growth requires a staged rollout contour. |
| `stable target switch --dry-run --json` | Deferred | Recovery target switching needs a separate UI safety contour. |
| `stable target switch --apply --json` | Deferred | Mutating recovery target switch needs a separate UI safety contour. |

If a UI workflow needs one of these surfaces, open a separate UI safety/spec
contour before implementation.

## Support/Open-File Actions

The UI may offer support actions:

- Open Logs
- Open State
- Open Registry
- Open Data Folder
- Open Diagnostics Bundle

Rules:

- open-file actions are operator support actions only
- open-file actions are shell/app open actions, not command API truth bindings
- they are not primary truth sources
- the UI may open files or folders for inspection
- the UI must not parse state files, registry files, diagnostics bundles, or logs
  to determine runtime health, account lifecycle, mode, rollout, or readiness
- diagnostics export must be treated as a redacted support artifact, not a
  health source

## Live-Gated Actions

The first UI implementation must not expose this as a normal button:

```sh
rollout evidence capture 16 --json
```

This command belongs to the live evidence lane. It requires the exact operator
marker:

```text
GO_FOR_LIVE_CAPTURE: run rollout evidence capture 16 --json once
```

No generic phrase such as `start`, `go`, `begin`, or `run it` authorizes live
capture. A future advanced/operator mode may reference live evidence only after
a separate approved contour.

## Screen Map

The first UI contour may plan these screens:

- Main Runtime Status
- Mode Controls
- Account Pool
- Onboarding
- Diagnostics
- Settings

This specification does not define visual design, layout polish, component
implementation, framework choice, packaging, installer behavior, or release
artifact structure.

## Runtime Status Screen

The Runtime Status screen must read from `status --json`, with optional
operator-triggered detail from `healthcheck --json`.

Required displayed fields when present:

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `next_action`
- `liveness`
- `severity`
- `operator_action`
- `desired_mode`
- `effective_mode`
- `endpoint`
- `current_proxy_url`
- `pool_summary.active`
- `pool_summary.reserve`
- `pool_summary.retired`
- `pool_summary.healthy`
- `pool_summary.degraded`
- `pool_summary.down`
- `attestation_summary`
- `last_error`

When an `attestation` object is present, the UI must handle these fields:

- `listener_ok`
- `models_ok`
- `responses_ok`
- `effective_mode_match`
- `base_url_match`
- `selected_backends_digest`
- `observed_at_utc`
- `runtime_version`
- `attestation_source`

Rules:

- show desired mode separately from effective mode
- listener truth beats cached UI state
- stale, unknown, down, degraded, and healthy must be distinct
- missing required runtime fields render as unknown or integration failure
- status must be refreshed after every mutating action

## Mode Controls

Mode controls must show desired mode and effective mode as separate facts.

Buttons:

- Switch Stable
- Switch Managed
- Run Managed Sync
- Launch Client
- Smoke Test
- Stable Repair Dry Run
- Stable Repair Apply

Rules:

- switching mode changes desired mode only until effective mode is observed
- `Launch Client` success is bounded dispatch truth only
- `Smoke Test` is bounded runtime smoke evidence only
- stable repair apply requires explicit confirmation
- stable repair dry run is preferred before stable repair apply
- no button may claim that stable or managed runtime is healthy without fresh
  command evidence

## Account Pool Screen

The Account Pool screen must read account state from `accounts list --json`.

Required displayed fields when present:

- account id
- label
- lifecycle pool: active, reserve, retired
- manual hold
- status
- fail count
- success count
- last success
- last error
- cooldown until
- notes
- registry identity summary
- active, reserve, retired counts
- capacity target 20

Rules:

- capacity 20 is architecture capacity, not proof of 20-account operation
- promotion is not scale proof
- any action affecting active routing requires `accounts list --json` and
  `status --json` refresh
- retired accounts have no automatic return path
- reserve-first onboarding remains separate from promotion

Account actions:

- Validate
- Recheck
- Promote
- Demote
- Hold
- Release
- Retire

## Onboarding Screen

The Onboarding screen must call:

```sh
accounts onboard --json
```

Required displayed `onboarding_result` fields when present:

- `input_mode`
- `explicit_auth_ref`
- `new_backend_ids`
- `selected_backend_id`
- `selection_status`
- `reserve_first_enforced`
- `pool_after_onboarding`
- `validate_attempted`
- `validate_outcome`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `external_command_exit_code`
- `external_command_status`
- `active_routing_changed`
- `final_outcome`

Rules:

- new accounts must enter reserve first
- onboarding success does not imply active routing readiness
- ambiguous detection requires `operator_action = user_action`
- no-new-auth detection must not be displayed as success
- external command exit code alone is not final truth
- skipped sync must remain visible as skipped
- status proof failure must not be displayed as reserve-only success

## Diagnostics Screen

Diagnostics actions:

- Export Diagnostics Bundle
- Open Logs
- Open State
- Open Registry
- Open Data Folder

Rules:

- `diagnostics export --json` is the only diagnostics bundle export command
- diagnostics export must be redacted
- diagnostics bundles are support snapshots, not runtime truth
- logs may be opened for humans but must not be parsed as API
- sensitive values must not be shown unless already redacted by command output

## Settings Screen

Allowed first-pass settings:

- host client path
- data directory display
- probe limits display
- legacy import status as deferred

Rules:

- settings must not invent write paths
- settings must not mutate config files directly
- any setting that needs persistence requires a future command API contour
- legacy import implementation is deferred until a separate contour

## Field Mapping

Every command binding must handle these fields on success and failure:

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`

Runtime-related packets must also handle:

- `liveness`
- `severity`
- `operator_action`
- `desired_mode`
- `effective_mode`
- `endpoint`
- `attestation`
- `attestation_summary`
- `pool_summary`

The UI must treat missing required fields as an integration failure or unknown
state, not as success.

## Button Inventory

Primary first-pass buttons:

- Switch Stable
- Switch Managed
- Run Managed Sync
- Launch Client
- Smoke Test
- Stable Repair Dry Run
- Stable Repair Apply
- Add Account
- Validate Account
- Recheck Account
- Promote Account
- Demote Account
- Hold Account
- Release Account
- Retire Account
- Export Diagnostics Bundle
- Open Logs
- Open State
- Open Registry
- Open Data Folder

Deferred buttons:

- Policy Stage Set
- Rollout Stage Prove
- Rollout Stage Advance
- Stable Target Switch
- Live Evidence Capture
- Legacy Import

## Confirmation Rules

Confirmation is required for:

- mode changes
- managed sync
- host-client launch
- smoke test
- stable repair apply
- account onboarding
- account promotion
- account demotion
- account hold
- account release
- account retirement

Confirmation is not required for:

- status refresh
- healthcheck refresh
- accounts list refresh
- rollout rotation inspect
- account validate
- account recheck when it is an alias for account validate
- diagnostics export
- stable repair dry run
- open-file support actions

## Stale/Unknown Rendering Rules

Render states as follows:

- `healthy`: only from fresh successful command evidence
- `degraded`: command reports degraded or partial runtime evidence
- `down`: command reports down or listener absence
- `stale`: command reports stale or evidence freshness failure
- `unknown`: invalid JSON, missing required fields, contradictory packet shape,
  command unavailable, or unsupported command output

Invalid JSON handling:

- show integration failure
- do not parse stderr
- do not infer success from exit code alone
- do not keep previous green status as current truth
- require a fresh successful command packet before returning to healthy

## Forbidden UI Claims

The UI may reference the accepted ADR-0002 development scale proof as project
context, but it must not present that proof as current full-scale live
availability.

The UI must not claim:

- `PILOT_READY`
- `SCALE_COMPLETE`
- `STABLE_20_PROVED`
- `stable_16_proved`
- `stable_20_proved`
- `stable_10_proved`
- `stable_15_proved`
- `alpha-ready`
- `production_ready`
- `PASS`
- healthy without fresh command evidence
- launch client means full host-client session success
- onboarding means active routing readiness
- diagnostics export means runtime health
- 16-account field evidence means 20-account proof
- capacity 20 means active 20-account operation is proved
- accepted scale proof means the current account set is ready for another
  full-scale run

## No Direct Runtime File Reads As Truth

The UI may open files for operator inspection.

The UI must not parse these as primary truth:

- backend registry
- supervisor state
- runtime mode files
- runtime effective mode file
- managed config
- logs
- diagnostics bundles

Primary truth comes from strict JSON commands.

## No Log Parsing

Logs may be opened for support.

Logs must not drive:

- health status
- account status
- mode status
- rollout status
- diagnostics status
- readiness claims

## Acceptance Criteria For Future UI Implementation

A future UI implementation contour must prove:

- every command invocation uses `--json`
- stdout parsing accepts exactly one JSON object
- invalid JSON renders integration failure
- stderr is not parsed as machine truth
- no cached-green state survives failed refresh
- every mutating action performs required post-action refresh
- support/open-file actions remain separate from primary truth
- live evidence capture is not exposed without a separate approved contour
- no direct file read is used as primary runtime truth

## Out Of Scope

- UI implementation
- UI framework choice
- visual design
- Electron, Tauri, React, or native app scaffolding
- runtime code changes
- command API changes
- state schema changes
- installer/package work
- live evidence capture
- live auth import
- live proxy/config mutation
- new scale-to-20 proof
- legacy import implementation
- new command surfaces
