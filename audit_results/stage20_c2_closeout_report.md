<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# STAGE20_C2_STAGE_ADVANCE_LOCK_REPAIR Closeout

## Goal

Close the execution-core gap in `run_rollout_stage_advance()` so registry,
stage, pool-count, target-satisfied, and backend-eligibility preconditions are
observed only under `serialized_lock`.

## Result

- status: completed
- final verdict: `GO_STAGE20_C3_ROLLOUT_POSTURE_INSPECT`
- next action: open `STAGE20_C3_ROLLOUT_POSTURE_INSPECT`

## Verification

- tests:
  - `python3 -m unittest tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_rollout_stage_advance_20_reads_target_satisfied_preconditions_under_serialized_lock tests.test_cli.CliTests.test_rollout_stage_advance_20_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_rollout_stage_advance_20_returns_noop_when_target_is_already_satisfied tests.test_cli.CliTests.test_rollout_stage_advance_20_rejects_overfull_stage_as_already_satisfied`
  - observed result: `Ran 5 tests in 1.328s OK`
  - `python3 -m unittest -f tests.test_cli`
  - observed result: `Ran 333 tests in 152.375s OK`
- build:
  - `python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py`
  - observed result: passed
- manual:
  - diff reviewed
  - lock-boundary movement stayed inside `runtime.py`
  - one new regression test added in `tests/test_cli.py`
  - no reserve semantics rewrite
  - no UI or live work mixed into the contour
- live verification:
  - none; repo-only contour

## Artifacts

- spec:
  - `audit_results/stage20_c2_spec.md`
- packet:
  - `audit_results/stage20_c2_verification_packet.json`
- report:
  - `audit_results/stage20_c2_closeout_report.md`

## Independent Audit

- auditor: `Mendel`
  - identified the exact registry-backed precondition window before
    `serialized_lock`
  - confirmed minimal safe repair shape
- auditor: `Halley`
  - verdict: `SAFE`
  - no reserve semantics drift detected
  - new target-satisfied held-lock test judged sufficient

## Git

- branch: `codex/stage20-c2-stage-advance-lock-repair`
- commit: `aef164c` (primary artifact commit)
- pushed: yes
- pull request: `#37` draft, targeting `codex/stage20-c1-research-cleanup-canon`

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- runtime data committed: no

## Notes

- This contour does not add `rollout posture inspect`.
- This contour does not change reserve semantics.
- This contour closes only the owner-lock precondition gap.
