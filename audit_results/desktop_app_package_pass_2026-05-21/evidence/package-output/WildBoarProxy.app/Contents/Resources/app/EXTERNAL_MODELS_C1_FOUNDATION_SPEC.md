<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: External Models C1 Foundation

## Objective

Establish the canon-aligned foundation for the `external-models` namespace
without live provider integration, real sidecar process ownership, or engine
duplication.

## In Scope

- ADR boundary for the bounded compatibility adapter decision
- canonical command payload alignment with `COMMAND_API.md`
- `external-models` CLI namespace scaffold
- route schema v1
- split declarative route config from observed route state
- isolated `WBP_EXTERNAL_MODELS_*` path overrides
- route file lifecycle commands:
  - `add`
  - `list`
  - `update`
  - `remove`
  - `enable`
  - `disable`
- foundation commands:
  - `status`
  - `models`
  - `profile codex-desktop`
  - `evidence capture`
- zero-test green guard through real module-backed test surfaces

## Out of Scope

- real local proxy server
- live provider probes
- provider protocol translation
- live `validate`
- live `check`
- `start` / `stop`
- Codex config mutation
- UI
- installer automation

## Constraints

- `CLIProxyAPI` remains the engine.
- External-models commands must emit canonical command payload fields.
- Development and tests must not write to real `~/.wild-boar-proxy/*` paths.
- `routes.json` stores declarative config only.
- `state.json` stores observed state and policy only.

## Assumptions

- Current external lab remains isolated.
- C1 may add new control-layer path overrides when needed.
- Runtime integration claims remain gated after C1.

## Acceptance Criteria

- [ ] `external-models` commands emit the canonical command payload fields
- [ ] route lifecycle works on isolated local files only
- [ ] `routes.json` and `state.json` stay split by responsibility
- [ ] `profile codex-desktop` is non-mutating
- [ ] `evidence capture` writes local non-live evidence only
- [ ] zero-test green acceptance is impossible for the new CLI test module
- [ ] no real sidecar or provider translation is implemented in C1

## Verification

- tests:
  - `python3 -m unittest -q tests.test_external_agent_lab`
  - `python3 -m unittest -q tests.test_external_models`
  - `python3 -m unittest -q tests.test_cli_external_models`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
- manual:
  - inspect emitted JSON packets for canonical fields
  - inspect written `routes.json`, `state.json`, and evidence files in isolated temp paths
- live evidence:
  - none

## Open Questions

- Whether external-models should eventually share more path helpers with the
  broader runtime without widening engine coupling
- Whether later contours should normalize machine error code casing across the
  whole product surface
