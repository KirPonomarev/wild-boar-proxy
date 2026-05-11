# step67 diagnosis analysis

## factual baseline

- `step65` restored simultaneous green execution-core truth
- `step65` downstream observation still showed:
  - `LIVE_POSTURE_DRIFT_ONLY`
  - `reserve_candidate=""`
  - `reserve_live_capable_count=0`
- `step66` reopened Branch C and confirmed on fresh live truth:
  - execution-core preconditions stayed green
  - no explicit eligible reserve candidate exists
  - no lawful one-surface owner path exists for `onboard`, `demote`, or
    `release`

## contradiction check

The only plausible contradiction candidate is the relationship between:

- live packets labeled `LIVE_POSTURE_DRIFT_ONLY` while
  `reserve_candidate=""`
- tests that can emit `RESERVE_CANDIDATE_NOT_IDENTIFIED`

This is not a contradiction.

`wild_boar_proxy/runtime.py` evaluates posture branches in ordered form:

1. canonical stage mismatch
2. already on requested stage:
   - target counts satisfied -> `OK`
   - target counts not satisfied -> `LIVE_POSTURE_DRIFT_ONLY`
3. insufficient source-stage live-capable pool
4. source active window overfull -> `LIVE_POSTURE_DRIFT_ONLY`
5. no reserve candidate -> `RESERVE_CANDIDATE_NOT_IDENTIFIED`
6. rotation evidence insufficient
7. ready

Therefore `RESERVE_CANDIDATE_NOT_IDENTIFIED` is a later branch than some
`LIVE_POSTURE_DRIFT_ONLY` branches. Both outputs are compatible under different
live-state shapes.

The targeted tests exercise those shapes separately:

- `test_rollout_posture_inspect_20_reports_live_posture_drift_only`
- `test_rollout_posture_inspect_20_reports_reserve_candidate_not_identified`
- `test_rollout_posture_inspect_20_reports_insufficient_eligible_pool_for_step41_shape`

Owner-surface semantics also remain consistent with the stop:

- `accounts onboard --json` requires a real onboarding input and reserve-first
  proof
- `accounts release <id> --json` requires a held backend
- `accounts demote <id> --json` requires a lawful active-to-reserve target and
  explicit precondition proof

The fresh `step66` packet set fails all three in different ways.

## diagnosis verdict

Current Branch C stop is live-state-owned.
No real repo/canon contradiction is proven by the current artifacts.
The truthful result is to remain stopped until fresh reserve input or pool truth
changes.
