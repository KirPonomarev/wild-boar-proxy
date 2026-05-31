# RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_PROOF_GATE Closeout

Date: 2026-05-13

Head before artifacts: `3c29948`

Final state: `RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_PROOF_READY_FOR_OWNER_DECISION`

Recommendation: `RECOMMEND_REVERT_WITH_SEPARATE_RUNTIME_CONTOUR`

## Scope

This was a decision-only proof gate for the dirty `run_promote` hunk.

No runtime code was edited.

No tests were edited.

No UI or desktop files were edited.

The launch-dispatch dirty hunk remains separate and out of scope.

The generated evidence tail remains separate and out of scope.

## Findings

`run_promote` is defined at `wild_boar_proxy/runtime.py:11154-11159`.

Production callers found:

- `wild_boar_proxy/cli.py:332` calls direct `accounts promote` without `lock_acquired=True`
- `wild_boar_proxy/runtime.py:9319-9321` calls `run_promote(..., lock_acquired=True)` from `run_rollout_stage_advance`

The inspected `lock_acquired=True` caller set is bounded to the stage-advance owner path.

Direct `accounts promote` still requires selected-backend verification because the dirty hunk keeps `selected_backend_requirement_met = selected_backend_verified` when `lock_acquired` is false.

The stage-advance postflight path checks:

- policy stage
- promoted backend active pool placement
- active/reserve count step
- runtime attestation
- rotation status
- rollback readiness

But the inspected postflight path does not explicitly check:

- `requested_backend_id in selected_backend_ids`

That is the critical proof gap.

## Canon Assessment

The dirty hunk says selected-backend participation is validated by postflight checks.

The inspected postflight checks do not explicitly bind selected-backend participation to the requested backend id.

Rotation evidence can prove a multi-backend selected set is available and not outside active routing candidates, but the current postflight code does not make requested-backend membership a dedicated condition.

Under the fail-closed runtime canon, this should not be accepted as-is.

## Tests Run

Command:

```bash
python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_accounts_promote_policy_verification_failure_rolls_back tests.test_cli.CliTests.test_rollout_stage_advance_15_fails_on_postflight_contradiction_after_promotion tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion
```

Result:

- PASS
- 4 tests ran

These tests confirm important rollback behavior, but they do not close the selected-backend membership proof gap.

## Inspector Result

Read-only inspection result: mixed.

Passed:

- `run_promote` definition found
- caller set found
- `lock_acquired=True` bounded to stage advance
- rollback paths found
- relevant tests found

Failed:

- no explicit selected-backend postflight proof after `run_promote` in stage advance
- no top-level selected-backend proof for `requested_backend_id`

Independent artifact audit result: PASS.

Audit caveat:

- independent artifact audit was used for artifact consistency and recommendation support
- local git commands remain the source for current worktree truth
- local git status still shows `wild_boar_proxy/runtime.py` as dirty and unstaged

## Validation

Local validation performed:

- JSON validation for the proof matrix
- service-trace scan over both new artifacts
- token/local-path scan over both new artifacts
- `git diff --check` over `runtime.py` and both new artifacts
- staged scope check before commit

## Recommendation

Use a separate owner-approved runtime contour to revert only the `run_promote` lock-acquired selected-backend bypass hunk.

Alternative owner path:

Use a separate accept/fix runtime contour that adds explicit postflight proof and tests:

- stage advance fails when `requested_backend_id` is absent from `selected_backend_ids`
- stage advance succeeds only when the requested backend is present in selected-backend evidence
- direct promote remains strict
- rollback remains intact

Until then, UI/desktop work should continue to treat this runtime tail as unresolved.
