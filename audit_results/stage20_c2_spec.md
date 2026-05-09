<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: STAGE20_C2_STAGE_ADVANCE_LOCK_REPAIR

## Objective

Close the execution-core gap in `run_rollout_stage_advance()` so stage,
registry, pool-count, target-satisfied, and backend-eligibility preconditions
are observed under the same serialized owner boundary as the composite
stage-advance path.

## In Scope

- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`
- held-lock regression coverage for target-satisfied stage-20 preconditions
- contour verification and closeout artifacts

## Out of Scope

- reserve semantics rewrite
- `rollout posture inspect`
- candidate filtering unless proven inseparable from this fix
- UI work
- live mutation
- engine-layer changes
- broad runtime refactor

## Constraints

- repo-write contour only
- no live mutation
- no engine-layer work
- preserve current stage-advance canon
- full `tests.test_cli` must remain green

## Assumptions

- `STAGE20_C1_RESEARCH_CLEANUP_CANON` is closed
- current repo baseline for `tests.test_cli` is green
- external patch bundles are source material only, not merge authority

## Acceptance Criteria

- [ ] Precondition reads no longer happen before `serialized_lock(paths)`.
- [ ] Held lock blocks target-satisfied stage-20 advance truthfully.
- [ ] No reserve semantics drift is introduced.
- [ ] Existing stage-advance behavior remains canonical.
- [ ] `python3 -m unittest -f tests.test_cli` stays green.

## Verification

- tests:
  - targeted stage-advance lock tests
  - `python3 -m unittest -f tests.test_cli`
- build:
  - `python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py`
- manual:
  - inspect diff for lock-boundary-only movement
  - confirm no unrelated docs/UI/runtime work is mixed in
- live evidence:
  - none

## Open Questions

- Does this contour need a tiny `COMMAND_API.md` wording update, or is that
  better left to a later command-surface contour?
