<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Execution Core Gate Closure

## Objective

Harden the execution-core JSON command contract around `launch client --json`
parse failures and collect fresh owner-surface evidence to determine whether
`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` can be truthfully earned.

## In Scope

- make `launch client --json` malformed invocation return a canonical JSON packet
- preserve parser usage behavior for non-JSON invocations
- capture fresh owner-surface packets for:
  - `status --json`
  - `mode get --json`
  - `accounts list --json`
  - `rollout rotation inspect --json`
  - `healthcheck --json`
- record a gate verdict based on packet truth, not narrative

## Out of Scope

- Accounts screen implementation
- any rich UI expansion
- typography or design polish
- new command surfaces
- direct file/log truth
- live mutation contours beyond already admitted safe read-path commands

## Constraints

- follow `CANON.md` then `MASTER_PLAN.md`
- keep runtime/control repair separate from UI work
- strict JSON command surfaces remain the primary truth source
- if gate evidence stays contradictory, contour must close `RED`

## Assumptions

- malformed `launch client --json` is a legitimate execution-core defect because
  admitted consumers expect canonical JSON packets
- `rollout rotation inspect --json` is an authoritative gate input for current
  rollout contradiction status

## Acceptance Criteria

- [x] `python3 -m wild_boar_proxy launch client --json` emits a canonical JSON
      packet instead of empty stdout plus parser-only stderr
- [x] non-JSON parser rejection still includes usage text in stderr
- [x] targeted CLI/UI-shell/web-ui regression tests pass
- [x] fresh owner-surface packets are captured and validated as JSON
- [x] gate verdict is explicit and machine-carried

## Verification

- tests:
  - `python3 -m unittest tests.test_cli.CliTests.test_status_requires_json_flag tests.test_cli.CliTests.test_legacy_import_requires_json_flag tests.test_cli.CliTests.test_launch_client_missing_required_flag_still_emits_json_packet tests.test_ui_shell.JsonCommandRunnerTests tests.test_web_ui.WebUiTests`
- build:
  - not applicable
- manual:
  - `python3 -m wild_boar_proxy launch client --json`
- live evidence:
  - `audit_results/execution_core_gate_closure_status_packet.json`
  - `audit_results/execution_core_gate_closure_mode_packet.json`
  - `audit_results/execution_core_gate_closure_accounts_packet.json`
  - `audit_results/execution_core_gate_closure_rotation_packet.json`
  - `audit_results/execution_core_gate_closure_healthcheck_packet.json`
  - `audit_results/execution_core_gate_closure_launch_client_missing_flag_packet.json`

## Open Questions

- whether the current `ROTATION_EVIDENCE_CONTRADICTED` packet is the last blocker
  or only one of several remaining execution-core gate blockers
