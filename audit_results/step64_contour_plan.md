# step64 contour plan

- `contour_id`: `RESERVE_READINESS_RECOVERY_CONTOUR`
- `goal`: recover one explicit eligible reserve backend through one admitted owner surface or stop truthfully
- `mode`: `live-proof`
- `hard preconditions`:
  - `status --json` must remain green enough for reserve-readiness work
  - `healthcheck --json` must remain green enough for reserve-readiness work
  - `rollout rotation inspect --json` must remain green enough for reserve-readiness work
  - no mutation under unresolved `LOCK_HELD`
- `owner-surface discipline`:
  - primary candidate: `accounts onboard --json`
  - secondary candidates require fresh proof: `accounts demote <id> --json`, `accounts release <id> --json`
  - if no one-surface path exists, stop without mutation
- `stop rule used in this contour`:
  - if runtime truth or rotation truth regresses at preflight, stop before reserve-gap packet and before any live mutation
