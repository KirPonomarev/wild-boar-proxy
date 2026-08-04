<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B13 Sequential Workflow Runner Closeout

## Goal

Implement the user-defined sequential workflow runner: ordered steps with
independent request/dispatch IDs, dynamic role instructions, executable
`continue`/`fresh`/`fork` context policies with digest transitions, exactly
one repo-touching lease at a time, fail-fast ambiguity, persisted
intermediate receipts, no silent actor swap, and proven visible delivery.
Workflow V1 has no parallel repo steps.

## Result

- status: implemented and verified
- final verdict: `sequential_workflow_runner.py` executes ordered steps,
  each producing a distinct receipt with `dispatch_id`, `turn_id`,
  `workflow_run_id`, `step_request_id`, `slot_id`, `binding_id`,
  `binding_revision`, `assignment_id`, provider, dynamic role instruction,
  and the context-digest transition; `continue` chains digests, `fresh`
  restarts them, `fork` branches from a named step; ambiguity fails fast
  with intermediate receipts persisted and no substitute dispatch;
  provider mismatch is a hard `WORKFLOW_ACTOR_SWAP_VIOLATION`; repo steps
  use the B05 `RepoLease` (external holders block, the run releases on
  completion); final packet proves visible delivery
- closure state: CLOSED

## Contour Capsule

- goal: B13 sequential workflow runner
- branch: `codex/b13-sequential-workflow-runner`
- head: `ffc35f4fae93df54e03a8765fe17e971709248ef` (base before contour commit)
- touched files: `wild_boar_proxy/sequential_workflow_runner.py` (new),
  `tests/test_sequential_workflow_runner.py` (new),
  `audit_results/B13_SEQUENTIAL_WORKFLOW_RUNNER_SPEC_2026-08-03.md`,
  `audit_results/B13_SEQUENTIAL_WORKFLOW_RUNNER_closeout_2026-08-03.md`
- tests run: `tests/test_sequential_workflow_runner.py` (14); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: silent actor substitution, ambiguous results continuing,
  parallel repo steps, lease fencing violations, digest drift across
  context policies
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_sequential_workflow_runner.py` -> `14 passed` (3 sequential
    steps with distinct dispatch/turn ids and shared run id; dynamic role
    instructions in receipts; continue chains digests; fresh restarts;
    fork branches from a named step; unknown fork target fails; ambiguity
    fails fast with receipts kept and no third dispatch; ambiguity
    exception fails fast; actor swap hard failure; dispatch error stops
    with per-receipt code; repo lease blocked by external holder; lease
    acquired and released on completion; duplicate step ids rejected;
    invalid policy rejected; empty workflow rejected)
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
  - dispatch callable is a fake-adapter seam; no live provider dispatch

## Artifacts

- spec: `audit_results/B13_SEQUENTIAL_WORKFLOW_RUNNER_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: workflow V1 semantics enforced (no parallel repo steps,
  fail-fast ambiguity, one lease, no swaps)

## Git

- branch: `codex/b13-sequential-workflow-runner`
- commit: contour commit contains the runner, tests, spec, and closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (receipts carry output text only; no
  secret material)
- live-path mutation performed: no (fake dispatch seam only; repo lease is
  a controlled test root)
- shared-helper refactor introduced: no (B05 RepoLease reused as-is)
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine test iterations (packet `extra`
  flattening and blocked-lease packet fields)
- resume from here: CLOSED
