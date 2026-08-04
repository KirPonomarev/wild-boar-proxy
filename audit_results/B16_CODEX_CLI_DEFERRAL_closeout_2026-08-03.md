<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B16_OPTIONAL Isolated Codex CLI Deferral Closeout

## Goal

Record the default outcome `CODEX_CLI_EXTENSION=DEFERRED` for the
optional isolated Codex CLI with evidence. Execution requires a separate
exact owner marker, a dedicated account, a separate home, a file
credential store, and proof of no main-account/keyring reuse — none of
which exist; the owner approval marker is `NONE` and the owner safety
override forbids the main Codex surface.

## Result

- status: implemented and verified
- final verdict: `codex_cli_deferral.py` is a probe-free deferral module:
  it records the per-fact evidence (owner marker absent, dedicated account
  absent, separate home absent, file credential store absent, no
  main-account/keyring reuse proof, safety override in force,
  `CODEX_CLI_EXPERIMENT_APPROVAL=NONE`) and returns the terminal outcome
  `CODEX_CLI_EXTENSION=DEFERRED`; the safety override blocks deferral even
  if prerequisites were claimed; the module never touches the main Codex
  surface
- closure state: CLOSED
  (terminal outcome: CODEX_CLI_EXTENSION=DEFERRED)

## Contour Capsule

- goal: B16_OPTIONAL isolated Codex CLI deferral
- branch: `codex/b16-codex-cli-deferral`
- head: `357b436b4338e6384db899f7ef69b058e388d2e5` (base before contour commit)
- touched files: `wild_boar_proxy/codex_cli_deferral.py` (new),
  `tests/test_codex_cli_deferral.py` (new),
  `audit_results/B16_CODEX_CLI_DEFERRAL_SPEC_2026-08-03.md`,
  `audit_results/B16_CODEX_CLI_DEFERRAL_closeout_2026-08-03.md`
- tests run: `tests/test_codex_cli_deferral.py` (5); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: any Codex surface access, claiming admission without the
  exact owner marker
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_codex_cli_deferral.py` -> `5 passed` (default outcome
    DEFERRED; safety override blocks even with prerequisites; facts
    recorded verbatim; module never touches the Codex surface; packet
    contains no secrets or paths)
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - `evaluate_codex_cli_deferral()` -> `CODEX_CLI_EXTENSION=DEFERRED`
- live verification:
  - none; probe-free deterministic deferral

## Artifacts

- spec: `audit_results/B16_CODEX_CLI_DEFERRAL_SPEC_2026-08-03.md`
- packet: `evaluate_codex_cli_deferral()` packet (DEFERRED)
- report: B16 is closed as DEFERRED_BY_DEFAULT per plan; no Codex
  execution occurred (owner safety override honored)

## Git

- branch: `codex/b16-codex-cli-deferral`
- commit: contour commit contains the deferral module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (probe-free module; no Codex paths, no
  credential stores, no secrets in packets)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none
- resume from here: CLOSED
