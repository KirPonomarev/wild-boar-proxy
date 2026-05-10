CONTOUR:
ID:
RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR

Goal:
Remove `LIVE_POSTURE_DRIFT_ONLY` through one admitted owner surface or stop
truthfully, without expanding this contour into stage-20 re-entry, same-day
validation, or UI.

Preflight intent:
- capture mandatory read-only snapshot
- confirm whether posture lane is admissible
- mutate only if one-surface normalization remains canonically open

Observed preflight shift:
- runtime truth stayed green
- posture remained `LIVE_POSTURE_DRIFT_ONLY`
- rotation evidence reopened as `ROTATION_EVIDENCE_STALE`

Consequence:
- if bounded reread confirms stale rotation evidence, this contour stops before
  any posture mutation and hands off to the rotation-evidence reclear lane
