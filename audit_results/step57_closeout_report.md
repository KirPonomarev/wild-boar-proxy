ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR closed with one admitted live mutation.

Live operation:
- `python3 -m wild_boar_proxy sync --json`

Observed owner outcome:
- strict JSON owner packet returned `machine_error_code=OK`
- changed files were reported explicitly
- no second owner surface was used

What improved:
- `rollout rotation inspect --json.machine_error_code` moved from
  `ROTATION_EVIDENCE_STALE` to `OK`
- selected-backend snapshot freshness moved from `stale` to `fresh`
- rotation participation status became `available`

What regressed:
- postflight `effective_mode` moved from `stable` to `managed`
- postflight `claim_gate.status` moved from `clear` to `blocked`
- postflight `policy_drift.status` moved from `clear` to `detected`
- postflight stable-runtime consumer effective source no longer matched desired

Closeout verdict:
- `NO_GO_RUNTIME_REGRESSION`
- next lawful contour:
  `TOP_LEVEL_RUNTIME_TRUTH_REPAIR_CONTOUR`
