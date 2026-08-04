<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B16_OPTIONAL Isolated Codex CLI Deferral

## Objective

Record the default outcome `CODEX_CLI_EXTENSION=DEFERRED` for the
optional isolated Codex CLI. Execution would require a separate exact
owner marker, a dedicated account, a separate home, a file credential
store, and proof of no main-account/keyring reuse — none of which exist;
the owner approval marker is `NONE` and the owner safety override forbids
the main Codex surface. The deferral module records evidence and never
executes Codex.

## In Scope

- `wild_boar_proxy/codex_cli_deferral.py` (new):
  - `evaluate_codex_cli_deferral(...)`: records the deferral facts
    (owner marker absent, dedicated account absent, separate home absent,
    file credential store absent, no main-account/keyring reuse proof,
    safety override in force) and returns the terminal
    `CODEX_CLI_EXTENSION=DEFERRED` packet
  - fail-closed: no Codex process, no Codex path, no credential store is
    ever touched
- tests: `tests/test_codex_cli_deferral.py`
- B16_OPTIONAL spec + closeout in `audit_results/`

## Out of Scope

- any Codex CLI execution (forbidden by the owner safety override)
- live credential phases
- any canon change (no command/state schema touch)

## Constraints

- the module never runs, reads, or modifies anything under the main Codex
  surface (`~/.codex`, main auth stores, Keychain Codex credentials)
- DEFERRED is the default and only outcome without a new exact owner
  marker

## Assumptions

- owner approval marker is `NONE` (`CODEX_CLI_EXPERIMENT_APPROVAL=NONE`)
  and the owner safety override forbids the main Codex surface

## Acceptance Criteria

- [ ] deferral packet records per-fact evidence and the terminal outcome
      `CODEX_CLI_EXTENSION=DEFERRED`
- [ ] no Codex surface is touched (probe-free module)
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_codex_cli_deferral.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none

## Open Questions

- None blocking.
