CONTOUR:
ID:
RESERVE_READINESS_RECOVERY_CONTOUR

Goal:
Recover one explicit eligible reserve backend through one admitted owner surface
or stop truthfully, without expanding this contour into posture normalization,
stage-20 re-entry, same-day validation, or UI.

Immediate reason:
- `step69` closed:
  - `GO_RESERVE_READINESS_RECOVERY_CONTOUR`
- `step69` re-proved simultaneous green execution-core truth
- fresh downstream observation still showed:
  - outer posture label `LIVE_POSTURE_DRIFT_ONLY`
  - narrower blocker `reserve_candidate=""`
  - `reserve_live_capable_count=0`

Mode:
live-proof

Primary candidate owner surface:
- `accounts onboard --json`

Secondary candidate owner surfaces:
- `accounts demote <id> --json`
- `accounts release <id> --json`

Execution shape:
1. Capture fresh preflight packets:
   - `status --json`
   - `healthcheck --json`
   - `accounts list --json`
   - `rollout rotation inspect --json`
   - `rollout posture inspect 20 --json`
2. Build reserve-gap packet and determine whether one explicit reserve candidate
   is already present or recoverable via exactly one lawful owner surface.
3. If lawful:
   - declare exact owner surface, write surfaces, rollback expectation
   - execute exactly one recovery step
4. Reread:
   - `status --json`
   - `healthcheck --json`
   - `accounts list --json`
   - `rollout rotation inspect --json`
   - `rollout posture inspect 20 --json`
5. Close with factual reserve-readiness verdict.

Primary success criteria:
- one explicit eligible reserve backend is truthfully present after recovery
  or is truthfully already present without mutation
- top-level runtime truth does not regress
- rotation evidence does not regress
- no silent active-routing change occurs
- partial or inferred reserve readiness is not success
