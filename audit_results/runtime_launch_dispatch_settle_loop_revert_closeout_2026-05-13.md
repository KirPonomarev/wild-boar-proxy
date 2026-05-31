# RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_REVERT Closeout

Date: 2026-05-13

Head before revert: `38a4331`

Final state: `TRACKED_RUNTIME_TAIL_CLEAN_FOR_UI_RESUME_REVIEW`

## Scope

This was a fail-closed revert contour for the remaining tracked runtime tail.

Changed locally:

- `wild_boar_proxy/runtime.py`

Artifacts:

- `audit_results/runtime_launch_dispatch_settle_loop_revert_matrix_2026-05-13.json`
- `audit_results/runtime_launch_dispatch_settle_loop_revert_closeout_2026-05-13.md`

Not changed:

- tests
- UI files
- desktop files
- generated evidence tail

No live runtime mutation was performed.

## Revert

Removed the 7-line `dispatch_external_client` settle loop:

- comment about short-lived probe scripts
- `settle_deadline = time.monotonic() + 1.25`
- `while` loop
- `process.poll()` check
- `time.sleep(0.01)`

Restored behavior:

- detached executable dispatch returns immediately after successful `subprocess.Popen`
- packet semantics remain:
  - `dispatch_method: detached_executable_spawn`
  - `dispatch_observed: true`
  - `dispatch_exit_code: null`
  - `stderr: ""`

## Runtime State

Post-revert check:

```bash
git diff -- wild_boar_proxy/runtime.py
```

Result:

- empty

Tracked runtime tail is clean.

This does not claim the full worktree is clean; generated/untracked evidence tail
remains separately out of scope.

## Tests

Command:

```bash
python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_treats_detached_executable_as_bounded_dispatch_only tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_cli.CliTests.test_launch_client_reports_exec_format_failure_as_json_packet tests.test_cli.CliTests.test_launch_client_blocks_dispatch_when_runtime_precondition_is_unhealthy tests.test_cli.CliTests.test_launch_smoke_reports_nonzero_launcher_even_if_runtime_is_healthy
```

Result:

- PASS
- 5 tests ran
- duration: 3.151 seconds

## Inspector

Pre-edit read-only inspector result: PASS.

The inspector confirmed:

- exactly one tracked runtime hunk before edit
- hunk was the 7-line settle loop in `dispatch_external_client`
- expected post-revert state was empty `git diff -- wild_boar_proxy/runtime.py`

## Validation

Local validation to complete before commit:

- JSON matrix validation
- `git diff --check`
- staged allowlist check, with only the two revert artifacts staged
- privacy/service trace scan
- token/local-path scan
- independent post-edit audit

## Follow-up

Next recommended contour:

`TRACKED_RUNTIME_TAIL_CLEAN_UI_RESUME_REVIEW`
