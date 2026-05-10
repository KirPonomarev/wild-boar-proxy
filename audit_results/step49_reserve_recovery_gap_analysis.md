CONTOUR_ID: ELIGIBLE_RESERVE_POOL_READINESS_RECOVERY

SUMMARY:
- current reserve slot is not eligible
- dedicated posture owner surface is blocked by `INSUFFICIENT_ELIGIBLE_POOL`
- no existing reserve candidate is live-capable

RECOVERY PATH CLASSIFICATION:
- existing reserve candidate narrow recovery:
  - not admitted inside this contour because the current reserve backend is quota-exhausted and there is no single canon-backed reserve-specific repair owner surface for that case
- one-owner-surface reserve replenishment:
  - admitted through `accounts onboard --json`
  - this remains the only canon-backed external owner surface for reserve-first onboarding truth

RECOVERY DECISION:
- attempt exactly one owner surface:
  - `accounts onboard --json --non-interactive`
- rationale:
  - one surface
  - reserve-first guardrails are owned there
  - avoids hidden active-routing selection
  - can fail honestly with machine-readable packet if no new auth/backend is produced
