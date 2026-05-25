<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WBP Native Codex Launch Contract

## Objective

Define the contract-only boundary for WBP-managed native Codex launch claims.
This spec prevents web workbench, process-only, or protected-baseline evidence
from being counted as a complete native Codex app launch.

## In Scope

- Two launch modes: `CODEX_CUSTOM_NATIVE_APP` and `ORIGINAL_CODEX_VIA_WBP`.
- Client command field allowlist.
- Server-owned authority boundary for paths, env, endpoint, route, backend, and process identity.
- Native launch claim packet identity chain.
- Contract validation tests for false-green substitutions.

## Out of Scope

- Live `Codex.app` launch.
- Runtime mutation.
- UI wiring or UI polish.
- Account onboarding.
- Universal API onboarding.
- Final E2E proof.
- Screenshots.

## Constraints

- `CLIProxyAPI` remains the engine; Wild Boar Proxy remains the control layer.
- Packet truth is stronger than screenshots or narrative.
- This spec is a contract artifact, not a roadmap or future execution queue.
- A native app claim must bind WBP action, process, window, profile, route endpoint, and trace identity.

## Acceptance Criteria

- [ ] The contract accepts exactly two launch modes.
- [ ] Client/browser payload cannot supply backend, route, endpoint, env, path, profile, or process authority.
- [ ] Custom native mode requires isolated `HOME`, isolated `CODEX_HOME`, isolated profile/data dir, and server-owned route configuration.
- [ ] Original via WBP mode forbids custom `HOME`, custom `CODEX_HOME`, and permanent user config mutation.
- [ ] Process-only, workbench-only, and protected-baseline-only packets fail validation.
- [ ] Contract validation performs no live launch, runtime mutation, or UI mutation.

## Verification

- tests: `python3 -m unittest tests.test_native_launch_contract`
- build: not required for contract-only Python/JSON changes
- manual: inspect changed files for runtime/UI mutation
- live evidence: not run; live launch is outside this contract-only boundary

## Open Questions

- None for this contract boundary.
