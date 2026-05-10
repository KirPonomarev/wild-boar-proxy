CONTOUR_ID: STABLE_RUNTIME_CONSUMER_ACTIVATION_GAP_AND_TOP_LEVEL_POLICY_DRIFT_RECLEAR
CONTOUR_CLASS: LIVE_PROOF
CONTOUR_STATUS: CLOSED_NO_GO
PRIMARY_GOAL: Reclear top-level status lane with at most one contract-backed owner write step
PRIMARY_BLOCKER:
- `status --json.claim_gate.status=blocked`
- `status --json.policy_drift.status=detected`
CANON_POSITION:
- execution-core repair only
- no reserve-first normalization
- no stage-20 re-entry
- no same-day validation
- no UI
EXECUTION_RULE:
- one blocker
- one admitted write step or STOP_AND_DIAGNOSE
- one reread
- closeout
FACTUAL_PRECHECK:
- `status --json` still reports `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
- `rollout rotation inspect --json` reports `machine_error_code=OK`, `participation_status=available`, `evidence_freshness=fresh`
- contradiction with rotation lane was already classified as contractually separate truth domains
EXPECTED_ADMISSION_REQUIREMENT:
- a single owner command must be directly contract-backed for this blocker
- if no single owner command exists, no mutation is allowed
