<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Stage Advance Stable Auth Materialization Hardening

## Objective

Harden stable-auth inventory materialization in the rollout stage-advance path
so target writes use atomic discipline and admitted write failures are reported
through `RuntimeErrorInfo` instead of leaking raw `OSError`.

## In Scope

- `materialize_rollout_stage_advance_stable_auth` in
  `wild_boar_proxy/runtime.py`.
- A local bytes atomic-write helper near the existing runtime atomic text/json
  helpers.
- Targeted tests in `tests/test_runtime_native_auth_recovery.py` for:
  - stable auth write failure packetization
  - unchanged chatgpt-to-codex materialization
  - no rewrite when target bytes are already current

## Out of Scope

- `stage_stable_repair_inventory`.
- Review bridge, MCP delegate, and proof/evidence artifact writers.
- UI, docs expansion, release-process redesign, or shared helper refactors.
- Live host-app mutation.

## Constraints

- Follow canon in this order: `CANON.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Preserve existing `STAGE_ADVANCE_STABLE_INVENTORY_VERIFY_FAILED` semantics.
- Preserve successful materialization result fields and output JSON shape.
- Keep verification fixture-backed unless a broader release gate is explicitly
  needed.

## Assumptions

- The source auth file exists and remains the authority for output mode.
- Caller behavior in `run_rollout_stage_advance` already handles
  `RuntimeErrorInfo` for this stage.
- A local helper is sufficient for this contour; a shared bytes helper can be
  considered only in a separate bounded contour.

## Acceptance Criteria

- [ ] Stable auth target writes use unique sibling temp file, flush/fsync,
      atomic replace, and temp cleanup on failure.
- [ ] Write failure returns `RuntimeErrorInfo` with
      `STAGE_ADVANCE_STABLE_INVENTORY_VERIFY_FAILED`.
- [ ] Successful chatgpt-to-codex materialization remains unchanged.
- [ ] Already-current target bytes do not trigger an unnecessary rewrite.
- [ ] Targeted tests, caller slice, compileall, diff check, and full pytest pass.

## Verification

- tests:
  - `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py`
  - `python3 -m pytest -q tests/test_runtime_native_auth_recovery.py -k 'stage_advance_materialization'`
  - `python3 -m pytest -q tests/test_cli.py::CliTests::test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization tests/test_cli.py::CliTests::test_rollout_stage_advance_20_accepts_already_materialized_stable_auth tests/test_cli.py::CliTests::test_rollout_stage_advance_15_accepts_already_materialized_stable_auth`
  - `python3 -m pytest -q`
- build:
  - `python3 -m compileall -q wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py tests/test_cli.py`
- manual:
  - `git diff --check -- wild_boar_proxy/runtime.py tests/test_runtime_native_auth_recovery.py`
  - direct fault-injection probe proving `RuntimeErrorInfo` instead of raw
    `OSError`
  - success probe proving materialized JSON still reports `type: codex`
- live evidence:
  - no live mutation in this contour

## Open Questions

- No open question is admitted for this contour.
