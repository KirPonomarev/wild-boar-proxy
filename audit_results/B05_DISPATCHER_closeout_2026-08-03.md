<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B05 Dispatcher, Assignments, Permissions, Diagnostics Closeout

## Goal

Implement the generic fail-closed actor dispatcher (alias/binding/assignment/
context resolution, permission intersection, one repo lease, strict errors,
dispatch diagnostics, no fallback/imitation) and update the command contract.

## Result

- status: implemented and verified
- final verdict: `actor_dispatcher.py` resolves canonical and legacy aliases
  into bounded dispatch plans with conservative permission intersection,
  strict fail-closed errors, and no-fallback truth; `repo_lease.py` provides
  the exclusive serialized repo lease with fencing-token release; the
  `dispatch resolve <alias> --json` read surface is documented in
  `COMMAND_API.md`
- closure state: CLOSED

## Contour Capsule

- goal: B05 dispatcher, assignments, permissions, diagnostics
- branch: `codex/b05-dispatcher`
- head: `1e478a78b29d372441ac9990b175126c35e4a68c` (base before contour commit)
- touched files: `wild_boar_proxy/actor_dispatcher.py` (new),
  `wild_boar_proxy/repo_lease.py` (new), `wild_boar_proxy/cli.py`,
  `COMMAND_API.md`, `tests/test_actor_dispatcher.py` (new),
  `audit_results/B05_DISPATCHER_SPEC_2026-08-03.md`,
  `audit_results/B05_DISPATCHER_closeout_2026-08-03.md`
- tests run: `tests/test_actor_dispatcher.py` (18 tests); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: permission escalation via role/assignment, unknown-alias
  passthrough, stale-route acceptance, fork without context digest, parallel
  repo writers, fallback/imitation substitution
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_actor_dispatcher.py` -> `18 passed`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> full local baseline green
- build:
  - `make check` (compileall + collect) green
- manual:
  - CLI smoke: `dispatch resolve` no-state -> `ALIAS_UNKNOWN` (fail closed);
    canonical registry -> `DISPATCH_PLAN_READY` with `binding-agent_1` /
    `dip` / `exit_code=0`; unknown alias -> `ALIAS_UNKNOWN`
  - `git diff --check` clean
- live verification:
  - no live mutation; no provider dispatch performed

## Artifacts

- spec: `audit_results/B05_DISPATCHER_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: `COMMAND_API.md` gained the `dispatch resolve <alias> --json`
  owner surface section (canon digest transition recorded in execution
  state)

## Git

- branch: `codex/b05-dispatcher`
- commit: contour commit contains modules, tests, spec, closeout, and the
  command contract update
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (dispatch plans expose no credentials, raw
  backend details, or paths)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: legacy-projection resolution originally defaulted the
  permission ceiling to `none`; aligned to the canonical migration default
  (`context_only`) so legacy resolution matches post-migration behavior;
  fencing token is returned to the lease holder as the release identity
- resume from here: CLOSED
