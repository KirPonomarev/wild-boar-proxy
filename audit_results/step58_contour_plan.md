CONTOUR:
ID:
TOP_LEVEL_RUNTIME_TRUTH_REPAIR_CONTOUR

Goal:
Restore top-level runtime truth through one admitted owner lane after the
post-sync regression, without expanding this contour into rotation reclear,
posture normalization, stage-20 re-entry, same-day validation, or UI.

Admitted owner lane:
- `python3 -m wild_boar_proxy launch smoke --json`

Preflight basis:
- `step57` closed `NO_GO_RUNTIME_REGRESSION`
- `step58_preflight_packets.json` shows:
  - `effective_mode=managed`
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
  - `stable_runtime_consumer.consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
  - rotation evidence already `OK`

Scope:
- one live owner-surface step only
- one postflight reread only
- factual closeout only

Stop conditions:
- invalid JSON from any owner surface
- contradictory canon proof that `launch smoke --json` is not admitted for the
  current activation lane
- broader runtime regression during or after the admitted step
