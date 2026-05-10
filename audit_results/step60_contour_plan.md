CONTOUR:
ID:
ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR

Goal:
Refresh selected-backend snapshot evidence through the sync owner lane, removing
`ROTATION_EVIDENCE_STALE` without expanding this contour into posture
normalization, stage-20 re-entry, same-day validation, or UI.

Preflight basis:
- `step59` stopped because posture work was not admissible on a stale rotation
  snapshot gate
- `step60_preflight_packets.json` shows:
  - top-level runtime truth green
  - `rollout rotation inspect --json -> ROTATION_EVIDENCE_STALE`
  - `selected_backend_snapshot_stale`

Scope:
- one live owner-surface step only
- one postflight reread only
- factual closeout only

Stop conditions:
- invalid JSON from any owner surface
- contradictory runtime truth before mutation
- `sync --json` fails to return a strict JSON owner packet
