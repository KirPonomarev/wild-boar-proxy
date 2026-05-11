CONTOUR:
ID:
COMPOSITE_RUNTIME_RECONCILIATION_PROOF_CONTOUR

Goal:
Prove or disprove simultaneous green convergence of
`sync --json -> launch smoke --json`.

Immediate reason:
- `step61` selected:
  - `GO_COMPOSITE_RUNTIME_RECONCILIATION_PROOF_CONTOUR`
- blind single-lane retries are no longer sufficient
- this contour exists to test one explicitly admitted bounded owner sequence

In scope:
- preflight packets
- explicit two-step owner declaration
- exactly one ordered live sequence:
  - `sync --json`
  - bounded midflight `rollout rotation inspect --json`
  - `launch smoke --json`
- final postflight packets
- targeted contract tests
- independent inspection
- factual closeout

Out of scope:
- posture normalization
- stage-20 re-entry
- same-day validation
- UI work
- repo contradiction repair implementation

Primary success criteria:
- final postflight shows:
  - `effective_mode=stable`
  - `claim_gate.status=clear`
  - `policy_drift.status=clear`
  - `stable_runtime_consumer.consumer_activation_readiness.machine_error_code=OK`
  - desired stable-runtime source equals effective source
  - `rollout rotation inspect --json.machine_error_code=OK`
  - `rotation_evidence_result.evidence_freshness=fresh`
- partial green is not success

Decision split:
- simultaneous green after the full sequence:
  - `GO_RESERVE_FIRST_LIVE_POSTURE_NORMALIZATION_CONTOUR`
- no simultaneous green after the full sequence:
  - `GO_OWNER_SURFACE_CONTRADICTION_REPAIR_CONTOUR`
- invalid owner packet or unsafe execution:
  - `STOP_AND_DIAGNOSE_SEQUENCE_EXECUTION_FAILED`
- broader unexpected runtime regression:
  - `NO_GO_RUNTIME_REGRESSION`
