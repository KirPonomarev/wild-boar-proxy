# RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_REVERT Closeout

Date: 2026-05-13

Head before revert: `cc6bd3d`

Final state: `RUNTIME_ROLLOUT_PROMOTE_LOCK_ACQUIRED_REVERTED_FAIL_CLOSED`

## Scope

This was a fail-closed revert contour.

Changed:

- `wild_boar_proxy/runtime.py`
- `audit_results/runtime_rollout_promote_lock_acquired_revert_matrix_2026-05-13.json`
- `audit_results/runtime_rollout_promote_lock_acquired_revert_closeout_2026-05-13.md`

Staged for commit:

- `audit_results/runtime_rollout_promote_lock_acquired_revert_matrix_2026-05-13.json`
- `audit_results/runtime_rollout_promote_lock_acquired_revert_closeout_2026-05-13.md`

`wild_boar_proxy/runtime.py` is intentionally not staged because after this revert
its only remaining diff is the out-of-scope launch-dispatch tail.

Not changed:

- UI files
- desktop files
- tests
- generated evidence tail
- launch-dispatch settle-loop hunk

No live runtime mutation was performed.

## Revert

The dirty `run_promote` lock-acquired selected-backend bypass was removed.

Removed from `run_promote`:

- `selected_backend_verified`
- `selected_backend_requirement_met`
- the `lock_acquired` branch that set `selected_backend_requirement_met = True`

Restored predicate:

```python
and backend_id in verified_selected_backend_ids
```

Result:

`run_promote` again requires the requested backend id to appear in `verified_selected_backend_ids` before `routing_change_observed` can become true.

## Remaining Runtime Tail

After this revert, the only remaining `runtime.py` diff is:

- `RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_DECISION`
- function: `dispatch_external_client`
- diff stat: 7 insertions

That hunk remains unresolved and still requires a separate owner decision.

## Tests

Command:

```bash
python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_accounts_promote_policy_verification_failure_rolls_back tests.test_cli.CliTests.test_rollout_stage_advance_15_fails_on_postflight_contradiction_after_promotion tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion tests.test_cli.CliTests.test_rollout_stage_advance_15_reports_truthful_changed_files_after_promotion tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step
```

Result:

- PASS
- 6 tests ran
- duration: 9.089 seconds

## Inspector

Pre-edit read-only inspector result: PASS.

The inspector confirmed:

- exactly two runtime diff hunks before edit
- lower hunk was the `run_promote` selected-backend bypass
- restored predicate should be `and backend_id in verified_selected_backend_ids`
- upper launch-dispatch settle-loop hunk should remain untouched

## Validation

Local validation to complete before commit:

- JSON matrix validation
- `git diff --check`
- staged allowlist check, with only the two revert artifacts staged
- privacy/service trace scan
- token/local-path scan
- independent post-edit audit

## Follow-up

Next unresolved runtime tail:

`RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_DECISION`
