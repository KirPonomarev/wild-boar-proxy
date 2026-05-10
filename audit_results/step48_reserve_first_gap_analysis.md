CONTOUR_ID: RESERVE_FIRST_POSTURE_NORMALIZATION

SUMMARY:
- reserve-first posture is not canonical yet
- reason is not top-level drift and not Lane A/Lane B regression
- reason is `INSUFFICIENT_ELIGIBLE_POOL`

FACTUAL BASIS:
- `status --json` is green at top-level:
  - `claim_gate.status=clear`
  - `policy_drift.status=clear`
- `rollout rotation inspect --json` is green:
  - `machine_error_code=OK`
  - `participation_status=available`
  - `evidence_freshness=fresh`
- `accounts list --json` shows:
  - one reserve backend exists
  - that reserve backend is `down`
  - last error class is `quota`
- `rollout posture inspect 20 --json` shows:
  - `machine_error_code=INSUFFICIENT_ELIGIBLE_POOL`
  - `reserve_live_capable_count=0`
  - `reserve_candidate_id=""`

CANON INTERPRETATION:
- reserve slot presence is not enough
- explicit eligible reserve backend is required for the next stage-20 contour
- branch `INSUFFICIENT_ELIGIBLE_POOL` in `NEXT_CONTOUR_CANON_PLAN.md` says:
  - stop
  - do not run stage advance
  - reopen only the blocking pool/readiness contour

NORMALIZATION ADMISSION:
- no one-step reserve-first normalization was admitted here
- current blocker is pool/readiness insufficiency, not a narrow posture flag drift
- `accounts onboard --json` is a separate owner surface for reserve-first onboarding truth and was not opened implicitly by this contour
