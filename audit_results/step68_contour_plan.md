# step68 contour plan

- `contour_id`: `FRESH_RESERVE_INPUT_OR_POOL_CHANGE_RECHECK_CONTOUR`
- `goal`: determine whether Branch C may lawfully reopen now
- `mode`: `read-only diagnosis`
- `scope`:
  - fresh read-only packet capture
  - comparison against `step66` Branch C baseline
  - fresh owner-surface admissibility check
  - no live mutation
- `expected early close`:
  - if execution-core regresses upstream, do not continue Branch C reopening
    logic; close on upstream blocker truth
