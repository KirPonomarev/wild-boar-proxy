# Independent Audit

## Scope

- contour: `STOP_AND_DIAGNOSE_SELECTOR_LOCK_HELD`
- branch: `codex/external-agent-lab-isolated`
- head basis: `fe19560`

## Independent Findings

- code-path audit:
  - `sync --json` is dispatched by [wild_boar_proxy/cli.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/cli.py:78)
  - `run_sync()` enters `with serialized_lock(paths):` in
    [wild_boar_proxy/runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:6756)
  - `serialized_lock()` raises `RuntimeErrorInfo(..., machine_error_code="LOCK_HELD")`
    only when the lock file exists and `process_is_alive(holder)` is true in
    [wild_boar_proxy/runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:5104)
  - the top-level JSON wrapper preserves that `machine_error_code` in
    [wild_boar_proxy/cli.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/cli.py:421)
- test-coverage audit:
  - sync-specific snapshot and healthcheck failure coverage existed
  - sync-specific held-lock and stale-lock coverage did not exist before this contour
  - the smallest missing guard was direct `sync --json` coverage for live lock
    and dead-pid stale lock

## Local Verification

- added [tests/test_cli.py](/Volumes/Work/wild-boar-proxy/tests/test_cli.py:14811)
  for `sync --json` under a live held lock
- added [tests/test_cli.py](/Volumes/Work/wild-boar-proxy/tests/test_cli.py:14828)
  for `sync --json` under a stale dead-pid lock
- passed targeted tests:
  - `test_sync_blocks_held_lock_without_mutation`
  - `test_sync_clears_stale_lock_and_proceeds_past_lock_gate`
  - `test_sync_returns_single_json_object`
  - `test_sync_materializes_selected_backend_snapshot_on_success`
  - `test_stable_repair_dry_run_blocks_held_lock_without_mutation`
  - `test_stable_repair_dry_run_blocks_stale_lock_without_mutation`

## Final Audit Verdict

- blocker classification: `true concurrent lock with post-packet release`
- stale-lock explanation: `rejected`
- code contradiction: `none found`
- packet ambiguity: `none found`
- final verdict: bounded selector retry is admissible
- next contour class: `SELECTOR_REFRESH_OWNER_PATH_PASS_RETRY_ONCE`
