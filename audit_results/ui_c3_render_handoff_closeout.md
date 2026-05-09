<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_C3_RENDER_HANDOFF_CONTRACT Closeout

## Goal

Prepare the exact render-handoff contract so incoming UI renders can be mapped
onto canonical screens, states, and command bindings without reopening truth
ambiguity, execution-core work, or scope chaos.

## Result

- status: completed
- final verdict: `RENDER_HANDOFF_READY`
- render base branch:
  - `codex/ui-c1-delivery-settlement`
- next contour:
  - `UI_RENDER_INTEGRATION_WHEN_RENDERS_ARRIVE`

## Verified Contract Outputs

- screen map fixed
- state matrix fixed
- command-binding matrix fixed
- allowed vs deferred action sets fixed
- render intake rules fixed
- render variant naming fixed

## Key Decisions

- first-pass required render screens:
  - `runtime-status`
  - `mode-controls`
  - `account-pool`
  - `diagnostics`
- conditional first-pass screens:
  - `onboarding`
  - `settings`
- `rollout posture inspect <15|20> --json` remains support-only and
  non-authoritative for UI render handoff
- `healthcheck-detail`, `rotation-detail`, and `stable-repair` are structural
  support panels already grounded in the current `ui_shell.py` surface
- deferred rollout and policy actions remain deferred and are not eligible for
  first-pass render integration

## Verification

- manual:
  - reviewed `UI_READINESS_SPEC.md` screen map, runtime rules, and deferred action set
  - reviewed `COMMAND_API.md` posture-classification authority rules
  - reviewed `wild_boar_proxy/ui_shell.py` actual bounded UI structure
  - confirmed render states are limited to states derivable from existing JSON packets
  - confirmed no new command surface was introduced
  - confirmed no `web_ui.py` scope drift was introduced
- commands:
  - `git diff --check`
  - observed result: passed

## Independent Fact Scan

- auditor: `Boyle`
  - grounded first-pass screens in repo/spec
  - confirmed primary truth commands and approved mutating set
  - confirmed deferred rollout actions remain deferred
  - confirmed `rollout posture inspect` is support-only in the UI handoff lane

## Independent Audit

- auditor: `Halley`
  - verdict: `SAFE`
  - confirmed:
    - no canon or scope drift
    - render states stay limited to existing JSON-grounded truth
    - `rollout posture inspect` remains support-only and non-authoritative
    - no `web_ui` or runtime expansion slipped into the contour

## Artifacts

- spec:
  - `audit_results/ui_c3_render_handoff_spec.md`
- packet:
  - `audit_results/ui_c3_render_handoff_packet.json`
- report:
  - `audit_results/ui_c3_render_handoff_closeout.md`

## Scope Check

- render implementation mixed in: no
- `web_ui.py` touched: no
- runtime or CLI repair mixed in: no
- new command surfaces invented: no
- deferred actions promoted into first-pass UI: no

## Notes

- this contour makes render intake safe but does not implement any render
- incoming render variants should use the fixed machine-friendly naming scheme:
  - `<screen>__<state>__<viewport>`
- render integration can now begin when renders are delivered onto the isolated
  UI base
