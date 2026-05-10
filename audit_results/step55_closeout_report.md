ROTATION_EVIDENCE_STALE_RECLEAR_CONTOUR closed without live mutation.

Reason:
- the contour premise was invalidated by a more upstream blocker than stale
  rotation evidence
- fresh preflight and bounded reread both showed reopened top-level runtime
  truth regression
- `claim_gate.status` remained `blocked`
- `policy_drift.status` remained `detected`
- `stable_runtime_consumer.consumer_activation_readiness` remained
  `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
- `rollout rotation inspect --json` also remained stale, but this stayed
  secondary after the runtime-truth reopen

What was preserved:
- fresh preflight packet bundle
- bounded status reread
- bounded healthcheck reread
- bounded rotation reread
- independent inspection with accepted and narrowed claims separated

What did not happen:
- no `sync --json`
- no owner-surface mutation
- no manual registry/state edits
- no posture normalization
- no stage-20 activity

Closeout verdict:
- `NO_GO_CONTOUR_PREMISE_INVALIDATED`
- primary blocker at this step:
  `TOP_LEVEL_RUNTIME_TRUTH_REOPENED`
- next lawful contour:
  `TOP_LEVEL_RUNTIME_TRUTH_REPAIR_CONTOUR`
