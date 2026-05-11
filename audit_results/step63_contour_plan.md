CONTOUR:
ID:
RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR

Goal:
Remove `LIVE_POSTURE_DRIFT_ONLY` through one admitted owner surface or stop
truthfully.

Immediate reason:
- `step62` converged runtime truth and rotation evidence
- fresh `step63` read-only truth remains:
  - `status --json` -> green
  - `healthcheck --json` -> green
  - `rollout rotation inspect --json` -> green
  - `rollout posture inspect 20 --json` -> `LIVE_POSTURE_DRIFT_ONLY`

Execution shape:
- capture fresh read-only snapshot
- resolve any transient `LOCK_HELD` before decision
- build normalization decision packet
- execute one owner-surface move only if canonically admissible
- otherwise stop without mutation

Planned success criteria:
- posture blocker clears without regressing runtime truth or rotation evidence

Observed closeout:
- fresh normalization packet did not name an explicit reserve candidate
- no one-surface normalization path was admitted
- no mutation was executed
