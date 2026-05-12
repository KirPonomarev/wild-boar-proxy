# RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_PROOF_GATE Closeout

Date: 2026-05-13

Head before artifacts: `9f248c9`

Final state: `RUNTIME_LAUNCH_DISPATCH_SETTLE_LOOP_PROOF_READY_FOR_OWNER_DECISION`

Recommendation: `RECOMMEND_REVERT_WITH_SEPARATE_RUNTIME_CONTOUR`

## Scope

This was a decision-only proof gate for the remaining `dispatch_external_client`
settle-loop tail.

No runtime code was edited.

No tests were edited.

No UI or desktop files were edited.

No live runtime mutation was performed.

## Findings

The remaining dirty hunk is in `wild_boar_proxy/runtime.py`.

Function:

- `dispatch_external_client`

Dirty hunk:

- 7 inserted lines
- adds a bounded wait up to 1.25 seconds after detached `subprocess.Popen`
- breaks early if `process.poll()` observes that the process exited

Caller facts:

- the only direct production caller found is `run_launch_client`
- `launch client --json` is the command surface that reaches this path
- `run_launch_smoke` does not call this path directly or indirectly
- UI/Tk/web paths are consumers of the launch-client command, not separate runtime truth owners

Packet truth:

- the loop can observe quick process exit through `process.poll()`
- the detached return packet still reports:
  - `dispatch_observed: true`
  - `dispatch_exit_code: null`
  - `stderr: ""`
- no packet field carries the observed poll result

## Canon Assessment

The wait is bounded, but boundedness is not enough.

The canon risk is that the hunk observes process-exit truth and discards it while
the command packet still reports successful OS dispatch request.

`launch client --json` must remain bounded to dispatch truth only and must not
become runtime health or host-client session truth.

Because no command contract was found that requires this wait, the fail-closed
recommendation is revert in a separate owner-approved runtime contour.

## Tests Run

Command:

```bash
python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_treats_detached_executable_as_bounded_dispatch_only tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_cli.CliTests.test_launch_client_reports_exec_format_failure_as_json_packet tests.test_cli.CliTests.test_launch_client_blocks_dispatch_when_runtime_precondition_is_unhealthy tests.test_cli.CliTests.test_launch_smoke_reports_nonzero_launcher_even_if_runtime_is_healthy
```

Result:

- PASS
- 5 tests ran
- duration: 4.138 seconds

These tests support the existing launch-client and launch-smoke boundary, but
they do not prove that the settle loop is required.

## Inspector Result

Read-only inspector result: `PASS_WITH_GAPS`.

Confirmed:

- `dispatch_external_client` definition and dirty hunk
- only direct production caller is `run_launch_client`
- `run_launch_smoke` does not reach `dispatch_external_client`
- settle loop observes process exit and discards that observation
- existing launch-client tests are present

Gaps:

- no proof that the wait is required
- no explicit packet truth field for quick detached-process exit
- no dedicated quick-exit truth test

Independent artifact audit result: PASS.

Audit caveat:

- independent artifact audit was used for artifact consistency and recommendation support
- local git commands remain the source for current worktree truth
- local git status still shows `wild_boar_proxy/runtime.py` as dirty with the launch-dispatch settle-loop hunk

## Validation

Local validation performed:

- JSON validation for the proof matrix
- service-trace scan over both new artifacts
- token/local-path scan over both new artifacts
- `git diff --check` over `runtime.py` and both new artifacts

## Recommendation

Use a separate owner-approved runtime contour to revert only the settle-loop hunk.

Alternative owner path:

Use a separate fix contour if the wait is truly needed, but that contour must add
explicit quick-exit packet truth and targeted tests.

Until then, UI/desktop work should continue to treat the runtime tail as unresolved.
