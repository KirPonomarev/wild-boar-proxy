<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B09 Generic One-Shot CLI Runtime

## Objective

Implement the server-owned one-shot CLI runtime that provider CLIs (Qwen
B10, Kimi B11, GLM B12) build on: server-owned tool manifest, sterile
probes (realpath/version/digest), scrubbed environments, isolated provider
homes, bounded process groups, sandbox seams, output parsers, cancellation,
presence-only auth sessions, and fake-adapter tests. One-shot sessions are
stateless: resume is never supported.

## In Scope

- `wild_boar_proxy/one_shot_cli_runtime.py` (new):
  - server-owned tool manifest (tool_id, bare binary name, version probe,
    supported output profiles); unknown tools fail closed
  - `resolve_tool_realpath` / `compute_tool_digest` (bounded sha256) /
    `run_sterile_probe` (version probe in sterile env)
  - `build_sterile_environment`: minimal PATH, secret-pattern env stripping,
    HOME redirected to the provider home, server-owned root override env for
    tests only
  - `create_provider_home`: isolated home + runtime dir, mode 0700, distinct
    per provider
  - `run_one_shot_cli`: bounded process group (start_new_session), timeout,
    output cap, `cancel()` via process-group SIGTERM then SIGKILL; returned
    run handle exposes `wait()` / `cancel()`
  - `parse_cli_output`: text / key-value / json-lines normalization with
    ANSI strip and caps; format detection is honest (unknown → raw)
  - sandbox profile: repo write default denied, repo read default none,
    OS-sandbox availability probed honestly (never claimed when absent)
  - one-shot auth sessions: presence-only record inside the provider home;
    secret values never appear in packets
  - one-shot run/session packets always carry `resume_supported: false`
    with reason `one_shot_sessions_are_stateless`
  - fake-adapter hook: test-only manifest override env
    (`WBP_ONE_SHOT_FAKE_MANIFEST`) so tests exercise the full runtime
    against a fake CLI without touching real binaries
- tests: `tests/test_one_shot_cli_runtime.py`
- B09 spec + closeout in `audit_results/`

## Out of Scope

- real Qwen/Kimi/GLM CLI bindings (B10/B11/B12)
- workflow runner (B13)
- persistent ACP (after one-shot stability, optional)
- isolated Codex CLI (B16, deferred)
- any canon change (no command/state schema touch)

## Constraints

- the manifest is server-owned; no operator-supplied tool definitions
- secrets and sensitive env vars never cross into the child environment or
  any packet
- process groups are bounded: timeout and cancel always terminate the whole
  group, never only the leader
- OS-sandbox claims are honest: absent enforcement is reported as
  declared-not-available, never simulated
- resume is never supported for one-shot sessions

## Assumptions

- provider CLIs accept a version/help probe in a sterile environment;
  first-launch config is contained by the isolated provider home
- fake-adapter tests are the honest proof surface for B09; real-binary
  probes are B10/B11/B12 scope

## Acceptance Criteria

- [ ] server-owned manifest resolves only declared tools; unknown tool ids
      fail closed
- [ ] sterile probe returns realpath, bounded digest, and version text
      without leaking env secrets to the child
- [ ] provider home is isolated, mode 0700, distinct home/runtime dirs
- [ ] bounded run: timeout, output cap, and process-group cancellation kill
      the whole group (leader and children)
- [ ] parsers normalize text/key-value/json-lines without fabrication
- [ ] auth session packets are presence-only; no secret values
- [ ] every one-shot run packet states `resume_supported: false`
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_one_shot_cli_runtime.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (fake-adapter controlled evidence only; real provider
  CLIs are B10/B11/B12)

## Open Questions

- None blocking.
