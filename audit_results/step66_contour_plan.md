# step66 contour plan

- `contour_id`: `RESERVE_READINESS_RECOVERY_CONTOUR`
- `goal`: recover one explicit eligible reserve backend through one admitted
  owner surface or stop truthfully
- `mode`: `live-proof`
- `preconditions`:
  - `status --json` green enough
  - `healthcheck --json` green enough
  - `rollout rotation inspect --json` green enough
  - no unresolved `LOCK_HELD`
- `owner-surface discipline`:
  - primary candidate: `accounts onboard --json`
  - secondary candidates only if fresh proof admits them:
    - `accounts demote <id> --json`
    - `accounts release <id> --json`
- `stop rule used in this contour`:
  - if fresh reserve-gap truth names no lawful one-surface path, stop without
    mutation and do not widen into posture normalization or stage-20
