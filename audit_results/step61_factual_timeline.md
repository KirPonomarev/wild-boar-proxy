Factual timeline:

1. `step58`
- `launch smoke --json` restored top-level runtime truth
- `effective_mode`: `managed` -> `stable`
- `claim_gate.status`: `blocked` -> `clear`
- `policy_drift.status`: `detected` -> `clear`
- `consumer_activation_readiness`: `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING` -> `OK`
- rotation remained `OK`

2. `step59`
- reserve-first posture normalization was not admissible
- top-level runtime truth remained green
- posture remained `LIVE_POSTURE_DRIFT_ONLY`
- mandatory snapshot gate reopened upstream:
  `rollout rotation inspect --json -> ROTATION_EVIDENCE_STALE`

3. `step60`
- `sync --json` repaired rotation freshness:
  - `rotation_machine_error_code`: `ROTATION_EVIDENCE_STALE` -> `OK`
  - `rotation_evidence_freshness`: `stale` -> `fresh`
- but top-level runtime truth regressed:
  - `effective_mode`: `stable` -> `managed`
  - `claim_gate.status`: `clear` -> `blocked`
  - `policy_drift.status`: `clear` -> `detected`
  - `consumer_activation_readiness`: `OK` -> `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`

Conclusion from timeline only:
- single-lane `launch smoke --json` can restore runtime truth
- single-lane `sync --json` can restore rotation freshness
- repeated split use of these lanes has not produced simultaneous green truth

