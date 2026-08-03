<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B09 Generic One-Shot CLI Runtime Closeout

## Goal

Implement the server-owned one-shot CLI runtime that provider CLIs (Qwen
B10, Kimi B11, GLM B12) build on: server-owned tool manifest, sterile probes
(realpath/version/digest), scrubbed environments, isolated provider homes,
bounded process groups, sandbox seams, output parsers, cancellation,
presence-only auth sessions, and fake-adapter tests. One-shot sessions are
stateless: resume is never supported.

## Result

- status: implemented and verified
- final verdict: `one_shot_cli_runtime.py` provides the generic runtime with
  an empty server-owned manifest (real provider tools are registered by
  B10/B11/B12) and a test-only fake-adapter hook; unknown tools fail closed;
  sterile probes return realpath/bounded-digest/version without leaking env
  secrets; provider homes are 0700-isolated with distinct runtime dirs;
  bounded runs and cancellation kill the whole process group; parsers
  normalize text/key-value/json-lines without fabrication; auth sessions are
  presence-only; every run/session packet states `resume_supported: false`
- closure state: CLOSED

## Contour Capsule

- goal: B09 generic one-shot CLI runtime
- branch: `codex/b09-one-shot-cli-runtime`
- head: `a71965955fb64454dae963c2d8a51ca6f6a1c6e4` (base before contour commit)
- touched files: `wild_boar_proxy/one_shot_cli_runtime.py` (new),
  `tests/test_one_shot_cli_runtime.py` (new),
  `audit_results/B09_ONE_SHOT_CLI_RUNTIME_SPEC_2026-08-03.md`,
  `audit_results/B09_ONE_SHOT_CLI_RUNTIME_closeout_2026-08-03.md`
- tests run: `tests/test_one_shot_cli_runtime.py` (18); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: env-secret leakage into children, unbounded process groups,
  fabricated parser output, simulated OS sandbox claims, resume support for
  one-shot sessions, operator-supplied tool definitions
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_one_shot_cli_runtime.py` -> `18 passed` (unknown tool fails
    closed; manifest server-owned with fake-adapter hook; sterile probe
    realpath/version/digest; missing binary; scrubbed env never leaks
    secrets incl. child-process evidence; provider home 0700 isolation;
    invalid provider id rejected; stdin/stdout capture; process-group
    cancellation via run and via handle; bounded timeout; honest output
    truncation; no-resume on run and receipt; parsers text/key-value/
    json-lines/auto with honest detection; presence-only auth session
    lifecycle; sandbox honesty incl. probed default; runtime receipt
    SYNTHETIC_PROVEN; stable env digest)
  - `make check` -> green (compileall + collect)
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
  - fake-adapter controlled evidence only (`declared_not_live_verified=true`);
    real provider CLI probes are B10/B11/B12 scope

## Artifacts

- spec: `audit_results/B09_ONE_SHOT_CLI_RUNTIME_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: runtime default sandbox probes OS enforcement honestly
  (`default_sandbox_profile`) instead of claiming a simulated profile;
  caller-supplied profiles are reported as given

## Git

- branch: `codex/b09-one-shot-cli-runtime`
- commit: contour commit contains the runtime module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (secret env vars stripped before children;
  auth sessions presence-only; secret values never appear in packets)
- live-path mutation performed: no (fake-adapter evidence only)
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine test iterations (packet `extra`
  flattening and sandbox-default honesty fixed during test development)
- resume from here: CLOSED
