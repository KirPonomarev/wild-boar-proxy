Contour `RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR` stopped before live
mutation.

Observed result:
- top-level runtime truth remained green
- posture remained `LIVE_POSTURE_DRIFT_ONLY`
- mandatory snapshot gate for posture work reopened upstream:
  - `rollout rotation inspect --json -> ROTATION_EVIDENCE_STALE`
  - bounded reread confirmed `selected_backend_snapshot_stale`

Independent inspection:
- reserve-candidate emptiness is real and remains relevant for a later posture
  contour
- but the current contour cannot truthfully reach that decision lane because
  stale rotation evidence blocks posture admissibility first

Next lawful contour:
- `ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR`
