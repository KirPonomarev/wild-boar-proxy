<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_C3_RENDER_HANDOFF_CONTRACT Spec

## Goal

Prepare the exact render-handoff contract so incoming UI renders can be mapped
onto canonical screens, states, and command bindings without reopening UI truth
ambiguity, execution-core work, or visual-scope chaos.

## Scope

- define the first render-integration screen set
- define required states per screen
- define command-binding matrix per screen
- define allowed vs deferred actions for render integration
- define render intake rules for incoming mockups and renders
- define render variant naming

## Explicitly Out Of Scope

- implementing renders
- touching `wild_boar_proxy/web_ui.py`
- redesigning `wild_boar_proxy/ui_shell.py`
- adding new command surfaces
- changing runtime truth contracts
- installer, package, or release work
- execution-core repair

## Render Base

- canonical render base branch:
  - `codex/ui-c1-delivery-settlement`
- canonical render base status:
  - `ready_clean_isolated_base`

## First-Pass Screen Map

Required first-pass screens for render intake:

- `runtime-status`
  - bound to `status --json`
  - may expose operator-triggered support detail from `healthcheck --json`
- `mode-controls`
  - bound to `mode get --json` plus approved mutating actions
  - includes structural support panels already grounded in `ui_shell.py`:
    - `launch-client`
    - `smoke-test`
    - `diagnostics-export`
    - `healthcheck-detail`
    - `rotation-detail`
    - `stable-repair`
- `account-pool`
  - bound to `accounts list --json`
- `diagnostics`
  - bound to `diagnostics export --json`
- `onboarding`
  - allowed only if the incoming render actually targets current bounded
    onboarding behavior already grounded in `accounts onboard --json`
- `settings`
  - display/support scope only
  - no new write paths
  - include only if the incoming render stays inside current bounded UI
    readiness scope

Not first-pass screens:

- any `web_ui` surface
- stage-proof UI
- stage-advance UI
- evidence-capture UI
- policy-stage mutation UI
- stable-target-switch UI

## State Matrix

Only states that can be truthfully derived from existing strict JSON command
surfaces may appear in render variants. No designer-only runtime states may be
invented.

### Runtime Status

- `healthy`
- `degraded`
- `down`
- `stale`
- `unknown`
- `integration-failure`

Required runtime distinctions:

- desired mode vs effective mode
- healthy vs degraded vs down vs stale vs unknown
- integration failure vs degraded runtime truth

### Mode Controls

- `desired-stable__effective-stable`
- `desired-managed__effective-managed`
- `desired-stable__effective-managed`
- `desired-managed__effective-stable`
- `action-result__ok`
- `action-result__recoverable-error`
- `action-result__user-action-required`
- `action-result__integration-failure`

### Launch Client Support Detail

- `bounded-dispatch-only`
- `failure`
- `integration-failure`
- `unknown`

Hard rule:

- `bounded-dispatch-only` is not launch success in the rich sense
- it must not be rendered as runtime health proof

### Smoke Test Support Detail

- `bounded-runtime-smoke-only`
- `failure`
- `integration-failure`
- `unknown`

Hard rule:

- `bounded-runtime-smoke-only` must not be rendered as global runtime success

### Account Pool

Pool and health distinctions that are already grounded in repo/spec:

- lifecycle pool:
  - `active`
  - `reserve`
  - `retired`
- hold state:
  - `hold`
  - `no-hold`
- backend health:
  - `healthy`
  - `degraded`
  - `down`
  - `probing`

### Onboarding

- `user-action-required`
- `reserve-only`
- `validate-attempted`
- `sync-skipped`
- `integration-failure`

Hard rules:

- no-new-auth detection must not render as success
- reserve-first remains visible
- onboarding must not imply active routing readiness

### Diagnostics

- `export-ready`
- `export-success`
- `export-failure`
- `integration-failure`

### Rollout Support Detail

Allowed only as support-only, non-authoritative detail:

- `healthcheck-detail`
- `rotation-detail`
- `posture-detail`

Hard rule:

- `rollout posture inspect <15|20> --json` remains support-only for UI handoff
- it must not replace:
  - `status --json`
  - `healthcheck --json`
  - `rollout rotation inspect --json`

## Command Binding Matrix

### Primary Truth

- `status --json`
- `healthcheck --json`
- `mode get --json`
- `accounts list --json`
- `rollout rotation inspect --json`

### Approved First-Pass Mutating Actions

- `mode set stable --json`
- `mode set managed --json`
- `sync --json`
- `launch client --json`
- `launch smoke --json`
- `stable repair --dry-run --json`
- `stable repair --apply --json`
- `accounts onboard --json`
- `accounts validate <id> --json`
- `accounts promote <id> --json`
- `accounts demote <id> --json`
- `accounts hold <id> --json`
- `accounts release <id> --json`
- `accounts retire <id> --json`
- `diagnostics export --json`

### Deferred Actions

- `policy stage set <10|15|20> --json`
- `rollout stage prove ... --json`
- `rollout stage advance ... --json`
- `rollout evidence capture 16 --json`
- `stable target switch ... --json`
- any action not already approved in `UI_READINESS_SPEC.md`

## Truth Rules

- top-level `machine_error_code` remains authoritative for any consumed command
- nested explanatory structures must not become competing truth surfaces
- invalid or malformed JSON is a hard integration failure
- logs, state files, cached UI state, and exit code alone are not truth sources
- `rollout posture inspect` remains support-only and non-authoritative for UI
  render handoff

## Structural Vs Decorative Elements

Structural elements:

- command-backed status labels
- liveness badges
- desired/effective mode fields
- account pool counts and lifecycle markers
- operator action and next-action surfaces
- action buttons backed by approved commands
- support-detail sections for healthcheck, rotation, onboarding, diagnostics

Decorative-only elements:

- backgrounds
- typography treatment
- spacing and framing
- non-semantic icons
- illustration and ornament

Decorative elements must not:

- imply forbidden claims
- hide authoritative truth placement
- visually collapse distinct runtime states into one success-looking state

## Render Intake Rules

- every incoming render must declare:
  - target screen
  - state variant
  - viewport scope
  - whether it is action-bearing or view-only
- every incoming render variant must use this naming rule:
  - `<screen>__<state>__<viewport>`
- example names:
  - `runtime-status__healthy__desktop`
  - `runtime-status__integration-failure__desktop`
  - `mode-controls__desired-stable__effective-managed__desktop`
  - `account-pool__degraded__desktop`
  - `diagnostics__export-success__desktop`
- if one composition contains multiple materially different states, it must be
  split into separate variants
- any render that introduces a deferred action must be tagged deferred, not
  silently accepted into first-pass implementation
- any render that visually claims:
  - `healthy`
  - `ready`
  - `proved`
  - `pilot-ready`
  - `20-account validated`
  without matching command truth must be rejected

## Acceptance Target

- first render-integration contour can start with no ambiguity about:
  - which screens are in scope
  - which states may be rendered truthfully
  - which commands bind each action
  - which actions remain deferred
  - how render variants are named
- no new truth surface is invented
- no `web_ui.py` scope drift is introduced
- `rollout posture inspect` remains support-only and non-authoritative
