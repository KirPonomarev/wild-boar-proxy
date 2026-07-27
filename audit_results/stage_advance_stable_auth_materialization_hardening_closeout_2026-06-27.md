<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Stage Advance Stable Auth Materialization Hardening Closeout

## Goal

Close the rollout stage-advance stable auth materialization write gap by using
atomic target writes and converting admitted write failures into the existing
`RuntimeErrorInfo` failure surface.

## Result

- status: implemented and verified
- final verdict: stable-auth materialization write failures are now
  packetizable through `STAGE_ADVANCE_STABLE_INVENTORY_VERIFY_FAILED`, successful
  materialization behavior is preserved, and the full pytest release gate is
  green
- closure state: CLOSED

## Contour Capsule

- goal: stage advance stable auth materialization hardening
- branch: `codex/stabilize-runtime-core`
- head: `e025724a0448befa9137b296a0c2a661525a04ab` before contour commit
- touched files: `wild_boar_proxy/runtime.py`, `tests/test_runtime_native_auth_recovery.py`, `audit_results/stage_advance_stable_auth_materialization_hardening_spec_2026-06-27.md`, `audit_results/stage_advance_stable_auth_materialization_hardening_closeout_2026-06-27.md`
- tests run: `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py`; `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py -k 'stage_advance_materialization'`; `python3 -m pytest -q tests/test_cli.py::CliTests::test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization tests/test_cli.py::CliTests::test_rollout_stage_advance_20_accepts_already_materialized_stable_auth tests/test_cli.py::CliTests::test_rollout_stage_advance_15_accepts_already_materialized_stable_auth`; `python3 -m compileall -q wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py tests/test_cli.py`; `git diff --check -- wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py`; `python3 -m pytest -q`
- blocked risks: raw stable-auth write `OSError`, non-atomic stable inventory target update, unnecessary rewrite of current stable auth target, materialization output drift, stale release-gate status
- closure state: CLOSED

## Verification

- tests:
  - `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py` -> `23 passed in 0.22s`
  - `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py -k 'stage_advance_materialization'` -> `3 passed, 20 deselected in 0.09s`
  - CLI stage-advance materialization slice -> `3 passed in 4.61s`
  - `python3 -m pytest -q` -> `4152 passed, 1 skipped, 952 subtests passed in 1049.29s (0:17:29)`
- build:
  - `python3 -m compileall -q wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py tests/test_cli.py`
- manual:
  - `git diff --check -- wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py` -> clean
  - direct forced `write_bytes_atomic` failure produced `RuntimeErrorInfo`, `STAGE_ADVANCE_STABLE_INVENTORY_VERIFY_FAILED`, `retry`
  - direct success probe materialized JSON with `type=codex`, `runtime_consumer_auth_normalized=True`, `runtime_consumer_auth_type=codex`
- live verification:
  - no live mutation was performed

## Artifacts

- spec:
  - `audit_results/stage_advance_stable_auth_materialization_hardening_spec_2026-06-27.md`
- packet:
  - no live packet artifact was required
- report:
  - full pytest release gate completed green after the code and test changes

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: the original direct probe reproduced raw `OSError` on
  stable auth target write; after the fix the same failure class is converted
  to the existing stage-advance stable inventory verification error surface
- resume from here: CLOSED
