CONTOUR:
ID:
ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR

Goal:
Refresh bounded rotation participation evidence through one admitted owner
lane, removing `ROTATION_EVIDENCE_STALE` without expanding into posture
normalization, stage-20, same-day validation, or UI.

Execution summary:
- capture fresh preflight packets
- confirm `sync --json` owner-lane admissibility only if runtime truth remains
  green enough
- if preconditions hold, execute exactly one `sync --json` write step
- otherwise stop before mutation and preserve evidence

Current outcome:
- fresh preflight captured successfully
- bounded reread confirmed top-level runtime truth reopened
- `claim_gate.status=blocked`
- `policy_drift.status=detected`
- `stable_runtime_consumer.consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
- no admitted owner surface selected
- contour closed `NO_GO_CONTOUR_PREMISE_INVALIDATED`
