<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B10_CODE Qwen One-Shot CLI Closeout

## Goal

Implement the isolated Qwen one-shot CLI layer on top of the B09 generic
runtime: `QWEN_HOME` / `QWEN_RUNTIME_DIR` isolation, project-config
denial/admission (`.qwen`, `.env`, extensions, plugins default-denied
unless individually admitted and digested), permission controls (repo write
denied by default), text / repo-read proof, denied-write proof, and timeout
/ cancel proof — all via fake-adapter controlled evidence. Real Qwen CLI
binary probe is B10_LIVE scope.

## Result

- status: implemented and verified
- final verdict: `qwen_one_shot_cli.py` provides the Qwen one-shot layer:
  sessions create a 0700 provider home with `QWEN_HOME` and
  `QWEN_RUNTIME_DIR` pointing inside it and a presence-only auth session;
  project configs are default-denied and admitted only with a digest that
  is re-checked against current file content (mismatch fails closed);
  repo write is denied by policy with honest OS-enforcement reporting;
  text, repo-read, denied-write, timeout, and cancel proofs are all
  fake-adapter controlled and declared-not-live; one-shot sessions never
  resume
- closure state: CLOSED

## Contour Capsule

- goal: B10_CODE Qwen one-shot CLI layer
- branch: `codex/b10-qwen-one-shot-cli`
- head: `794a915bd7ae69a9fa04aee6831342188b85e260` (base before contour commit)
- touched files: `wild_boar_proxy/qwen_one_shot_cli.py` (new),
  `tests/test_qwen_one_shot_cli.py` (new),
  `audit_results/B10_QWEN_ONE_SHOT_CLI_SPEC_2026-08-03.md`,
  `audit_results/B10_QWEN_ONE_SHOT_CLI_closeout_2026-08-03.md`
- tests run: `tests/test_qwen_one_shot_cli.py` (11);
  `tests/test_one_shot_cli_runtime.py` (18 regression); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: qwen config leakage from project roots, admitted config
  drift (digest mismatch), simulated OS sandbox claims, resume support for
  one-shot sessions, write permission bypass
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_qwen_one_shot_cli.py` -> `11 passed` (session isolation
    with QWEN_HOME/QWEN_RUNTIME_DIR inside the provider home and auth
    presence; qwen env points inside the provider home; project config
    default-denied incl. directory configs; admission with digest; digest
    mismatch fails closed; deny returns to default-denied; text proof;
    repo-read proof requires admission and matches admitted content;
    denied-write proof policy-level with honest OS enforcement; timeout
    proof; cancel proof; fail-closed without session; parsed output;
    declared-not-live receipt)
  - `tests/test_one_shot_cli_runtime.py` -> `18 passed` (B09 regression)
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - n/a
- live verification:
  - fake-adapter controlled evidence only
    (`declared_not_live_verified=true`); B10_LIVE is the credential-gated
    seam for the real Qwen CLI binary

## Artifacts

- spec: `audit_results/B10_QWEN_ONE_SHOT_CLI_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: the Qwen layer reuses the B09 runtime unchanged; all
  provider-specific behavior lives in the qwen module

## Git

- branch: `codex/b10-qwen-one-shot-cli`
- commit: contour commit contains the qwen one-shot layer, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (project configs denied by default;
  admissions are path+digest only; auth sessions presence-only; secret
  values never appear in packets)
- live-path mutation performed: no (fake-adapter evidence only)
- shared-helper refactor introduced: no (B09 runtime reused as-is)
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine test iterations (auth presence
  read via `one_shot_auth_status`; aggregate project-config policy stays
  error while individual admitted files are admitted)
- resume from here: CLOSED
