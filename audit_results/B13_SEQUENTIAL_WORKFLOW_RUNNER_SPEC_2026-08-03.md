<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B13 Sequential Workflow Runner

## Objective

Implement the user-defined sequential workflow runner: ordered steps with
independent request/dispatch IDs, dynamic role instructions, executable
`continue`/`fresh`/`fork` context policies with digest transitions, exactly
one repo-touching lease at a time, fail-fast on ambiguity, persistence of
intermediate receipts, no silent actor swap, and proven visible delivery.
Workflow V1 has no parallel repo steps.

## In Scope

- `wild_boar_proxy/sequential_workflow_runner.py` (new):
  - `WorkflowStep`: step_request_id, slot_id, binding_id, binding_revision,
    assignment_id, provider, role_instruction (dynamic, non-authoritative),
    context_policy (`continue` | `fresh` | `fork`), fork_from, prompt,
    repo_touching flag
  - `run_sequential_workflow`: ordered execution with per-step dispatch
    receipts carrying `dispatch_id`, `turn_id`, `workflow_run_id`,
    `step_request_id`, `slot_id`, `binding_id`, `binding_revision`,
    `assignment_id`, provider, role instruction, and the context-digest
    transition (previous -> new)
  - context policies: `continue` chains the digest from the previous step;
    `fresh` starts an independent digest; `fork` branches from a named
    step's digest
  - one repo lease: repo-touching steps use the B05 `RepoLease`; an
    externally held lease blocks the run (fail-fast); the run releases its
    lease on completion
  - fail-fast ambiguity: an ambiguous step result stops the run, keeps all
    intermediate receipts, and never substitutes another actor
  - actor-identity guard: a dispatch result from a provider different from
    the step's provider is a hard failure, never a swap
  - dispatch callable seam (fake adapter for tests) + workflow summary
    packet with proven visible delivery
- tests: `tests/test_sequential_workflow_runner.py`
- B13 spec + closeout in `audit_results/`

## Out of Scope

- parallel repo steps (Workflow V1 explicitly has none)
- automated native-primary workflow steps (disabled until physically
  proven)
- web workflow UI (B14)
- persistent workflow resume (workflow runs are completed or failed-fast;
  intermediate receipts are persisted in the run record)
- any canon change (no command/state schema touch)

## Constraints

- one manual addressed turn produces at most one dispatch; each workflow
  step is its own turn with its own `turn_id` and `dispatch_id`
- role instructions never grant permission (non-authoritative, per B05)
- the run stops after ambiguity, never silently swaps actors, and never
  falls back to local imitation
- at most one repo-touching lease is ever held by a run; external holders
  block repo steps
- all receipts are persisted in the run record before the next step starts

## Assumptions

- the dispatch callable is the seam for fake-adapter evidence; real
  provider dispatch already exists via the API transport adapter
  (B07/B08) and one-shot CLIs (B10/B11)

## Acceptance Criteria

- [ ] N sequential steps produce N distinct dispatch receipts with unique
      dispatch/turn ids and one shared workflow_run_id
- [ ] continue/fresh/fork produce the documented digest transitions
- [ ] ambiguous step fails fast: run stops, intermediate receipts kept,
      no substitute dispatch
- [ ] provider mismatch is a hard failure (no silent swap)
- [ ] repo lease: one at a time; external holder blocks; run releases on
      completion
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_sequential_workflow_runner.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (dispatch callable is a fake-adapter seam)

## Open Questions

- None blocking.
