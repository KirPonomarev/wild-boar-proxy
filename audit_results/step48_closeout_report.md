CONTOUR_ID: RESERVE_FIRST_POSTURE_NORMALIZATION
CLOSEOUT_STATUS: NO_GO_RESERVE_FIRST_STILL_INCOMPLETE

SUMMARY:
- reserve-first posture is not yet canonical
- no live normalization step was admitted
- stage-20 contour must not open next

PRIMARY FACTS:
- top-level runtime truth is green:
  - `claim_gate.status=clear`
  - `policy_drift.status=clear`
- Lane B remains green:
  - `rollout rotation inspect --json.machine_error_code=OK`
  - `participation_status=available`
  - `evidence_freshness=fresh`
- reserve posture owner packet is blocked:
  - `machine_error_code=INSUFFICIENT_ELIGIBLE_POOL`
  - `classification=INSUFFICIENT_ELIGIBLE_POOL`
  - `reserve_live_capable_count=0`
  - `reserve_candidate_id=""`
- reserve pool contains one backend, but it is not eligible:
  - backend id `k-gpt-pro`
  - status `down`
  - error class `quota`

CANON EFFECT:
- do not open `STAGE_20_OWNER_PATH_REENTRY`
- do not hide the stop behind UI work
- reopen only the blocking pool/readiness contour

INDEPENDENT INSPECTION:
- inspector `Hypatia` independently reached the same verdict:
  - reserve-first status = incomplete
  - explicit eligible reserve backend = no
  - live mutation admissible here = no
  - stage-20 may open next = no

NEXT LEGAL MOVE:
- open:
  - `ELIGIBLE_RESERVE_POOL_READINESS_RECOVERY`
- remain closed:
  - `STAGE_20_OWNER_PATH_REENTRY`
  - `SAME_DAY_20_ACCOUNT_VALIDATION`
  - `UI_*`
