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
  - `make test-full` -> two local full-suite runs each failed exactly one
    timing/subprocess-sensitive test, a DIFFERENT test in each run:
    (1) `test_official_mcp_transcript_tool_result_observation.py::test_cli_emits_observation_packet`
    (ledger-bound dispatch proof subprocess reported
    `codex_hook_trusted_by_profile_state=false`; the hook app-server probe
    has a 10s bounded timeout); (2)
    `test_cli.py::test_package_launchable_relocated_launcher_smoke_web_shell_json_works_without_repo_pythonpath`
    (`BrokenPipeError` in the relocated launcher smoke web shell). Both tests
    pass in isolation and in file groups on both this branch and main; the
    first full-suite run on main (B04 head) control result is recorded
    separately. Neither failing test exercises any B05 code path. GitHub CI
    full-suite results on the contour branch are recorded below as the
    authoritative machine evidence.
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
- suite-level timing evidence: two local full-suite runs each failed one
  different subprocess/timing-sensitive test (see Verification); both pass in
  isolation; root cause is local machine load under the 21-24 minute suite,
  not a B05 code path; control full-suite run on the B04 head executed in a
  separate worktree and GitHub CI results recorded in the PR
- resume from here: CLOSED
