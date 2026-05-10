Contour `ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR` repaired rotation evidence but
closed `NO_GO_RUNTIME_REGRESSION`.

Observed result:
- admitted owner lane `sync --json` returned strict JSON with
  `machine_error_code=OK`
- postflight `rollout rotation inspect --json` became `OK`
  - `participation_status=available`
  - `evidence_freshness=fresh`
- but top-level runtime truth regressed:
  - `effective_mode=managed`
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
  - `stable_runtime_consumer.consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`

Independent inspection:
- owner-lane facts converged with `sync --json` as the stale-evidence repair
  surface
- the inspector's authorization stop was narrowed because explicit live owner
  authorization exists in the active thread

Next lawful contour:
- `TOP_LEVEL_RUNTIME_TRUTH_REPAIR_CONTOUR`
