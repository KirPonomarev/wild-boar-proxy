CONTOUR_ID: MULTI_LANE_RUNTIME_RECLEAR_SPLIT_ADMISSION

LANE_A: stable_runtime_consumer activation lane
- packet basis:
  - `status --json.stable_runtime_consumer.desired_stable_runtime_consumer_source.source_kind=approved_repair_target`
  - `status --json.stable_runtime_consumer.effective_stable_runtime_consumer_source.source_kind=observed_stable_inventory_source`
  - `status --json.stable_runtime_consumer.consumer_activation_readiness.machine_error_code=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
  - `status --json.stable_runtime_consumer.activation_evidence_surface.status=snapshot_stale`
- repo semantic basis:
  - `COMMAND_API.md` says when desired source is approved repair target, `launch smoke --json` may materialize generated config, pass `WBP_STABLE_CONFIG`, and write `stable_runtime_consumer_snapshot`
  - `RUNTIME_CONTRACT.md` says approved-target activation success must remain separately observable from observed-source fallback
- owner surfaces:
  - primary activation owner: `launch smoke --json`
  - delegated recovery/attestation semantic owner: `healthcheck --json`
- lane status:
  - `LIVE_WRITE_CONTOUR_REQUIRED`

LANE_B: selected-backend snapshot / rotation evidence lane
- packet basis:
  - `rollout rotation inspect --json.machine_error_code=OK`
  - `rotation_evidence_result.participation_status=available`
  - `rotation_evidence_result.evidence_freshness=fresh`
  - `rotation_evidence_result.selected_backend_snapshot_validation_status=valid`
  - `rotation_evidence_result.evidence_source_name=sync --json`
- repo semantic basis:
  - `STATE_SCHEMA.md` says `supervisor-state.json.selected_backend_snapshot` may be materialized or refreshed only by `sync --json`
- owner surfaces:
  - primary write owner: `sync --json`
  - validation/readout owner: `rollout rotation inspect --json`
- lane status:
  - `GREEN_NO_WRITE`

LANE_C: top-level status / claim-gate / policy-drift lane
- packet basis:
  - `status --json.claim_gate.status=blocked`
  - `status --json.claim_gate.sources=["policy_drift"]`
  - `status --json.policy_drift.status=detected`
  - `status --json.policy_drift_observed.status=detected`
- repo semantic basis:
  - `wild_boar_proxy/runtime.py::get_claim_gate(...)` derives claim-gate from `policy_drift` and `registry_identity`
  - current packet source set contains only `policy_drift`
  - `wild_boar_proxy/runtime.py::summarize_status(...)` chooses top-level `policy_drift` via approved-target policy only when `require_live_stable_runtime=True` path passes
- owner surface:
  - readout owner: `status --json`
- lane status:
  - `DERIVED_BLOCKED_BY_UPSTREAM_LANE`
- derived-from:
  - Lane A first
  - not Lane B, because Lane B is already `OK/fresh`

NO_MERGE_GUARD:
- do not merge Lane A and Lane B into one live contour
- do not reopen one-step reclear fiction
