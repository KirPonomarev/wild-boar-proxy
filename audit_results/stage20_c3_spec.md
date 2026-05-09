<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: STAGE20_C3_ROLLOUT_POSTURE_INSPECT

## Objective

Add a read-only `rollout posture inspect <15|20> --json` owner surface so
stage-advance readiness can be classified explicitly without mutation and
without forcing operators to infer posture from multiple separate command
packets.

## In Scope

- `wild_boar_proxy/runtime.py`
- `wild_boar_proxy/cli.py`
- `tests/test_cli.py`
- `COMMAND_API.md`
- posture-specific verification and closeout artifacts

## Out of Scope

- live mutation
- hidden recovery or policy repair
- registry normalization
- reserve semantics rewrite
- engine-layer changes
- UI work
- broad runtime refactor

## Constraints

- repo-write contour only
- no live mutation
- top-level `machine_error_code` remains authoritative
- nested posture detail must not contradict top-level command truth
- `rollout posture inspect` must remain read-only in practice
- full `tests.test_cli` must remain green

## Assumptions

- `STAGE20_C2_STAGE_ADVANCE_LOCK_REPAIR` is closed
- current repo baseline for `tests.test_cli` is green
- external posture-classifier patches are source material only, not merge authority

## Acceptance Criteria

- [ ] `rollout posture inspect 15 --json` exists.
- [ ] `rollout posture inspect 20 --json` exists.
- [ ] The command returns strict JSON only.
- [ ] The command performs no runtime, registry, or policy writes.
- [ ] Top-level `machine_error_code` stays authoritative.
- [ ] Step41-shaped insufficiency is covered by tests.
- [ ] Stage-15 and stage-20 posture paths are both covered by tests.
- [ ] `python3 -m unittest -f tests.test_cli` stays green.

## Verification

- tests:
  - `python3 -m unittest tests.test_cli -k rollout_posture`
  - `python3 -m unittest tests.test_cli -k rollout_rotation_inspect`
  - `python3 -m unittest tests.test_cli -k stage_advance`
  - `python3 -m unittest -f tests.test_cli`
- build:
  - `python3 -m py_compile wild_boar_proxy/runtime.py wild_boar_proxy/cli.py tests/test_cli.py`
- manual:
  - inspect diff for read-only behavior only
  - confirm top-level/nested truth alignment
  - confirm no reserve semantics rewrite slipped in
- live evidence:
  - none

## Open Questions

- Does candidate-id blank filtering remain localized enough to defer to
  `STAGE20_C4_CANDIDATE_FILTERING`, or does later evidence show it should be
  folded into posture summaries?
