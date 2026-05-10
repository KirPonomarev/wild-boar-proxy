<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step44 Contract Mapping

## Reproduced Runtime Facts

- `status --json`
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
  - `policy_drift_observed.status=detected`
  - `effective_mode=managed`
  - `stable_runtime_consumer.effective_stable_runtime_consumer_source.status=observed_source_active`
  - `stable_runtime_consumer.consumer_activation_readiness.machine_error_code=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
- `rollout rotation inspect --json`
  - `machine_error_code=OK`
  - `rotation_evidence_result.policy_drift_status=clear`
  - `rotation_evidence_result.policy_drift_observed_status=detected`
  - `rotation_evidence_result.policy_drift_claim_surface_source=approved_repair_target`
  - `rotation_evidence_result.participation_status=available`
  - `rotation_evidence_result.evidence_freshness=fresh`

## Semantic Mapping

- `COMMAND_API.md`
  - `rollout rotation inspect --json` is a bounded read surface for rotation
    participation evidence truth.
  - it exposes nested `policy_drift_status` and participation evidence fields.
  - it remains a separate owner surface / separate gate.
- `wild_boar_proxy/runtime.py`
  - `status --json` computes both `policy_drift` and `policy_drift_observed`.
  - `status --json` selects approved-target `policy_drift` only if
    `should_use_approved_target_policy_drift(... require_live_stable_runtime=True ...)`
    passes.
  - `rollout rotation inspect --json` computes both selected and observed
    policy-drift surfaces too, but calls
    `should_use_approved_target_policy_drift(... require_live_stable_runtime=False ...)`.
  - `claim_gate` binds to top-level selected `policy_drift`, not observed drift.
- tests
  - `test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid`
    explicitly allows:
    - `status.policy_drift.status=clear`
    - `status.policy_drift_observed.status=detected`
    - `claim_gate.status=clear`
  - `test_rollout_rotation_inspect_uses_approved_target_policy_surface_when_activation_evidence_is_valid`
    explicitly allows:
    - `rotation.policy_drift_status=clear`
    - `rotation.policy_drift_observed_status=detected`
    - `rotation.machine_error_code=OK`

## Classification Meaning

These two fields do not live under one forced-equality contract:

- `status --json.policy_drift`
- `rollout rotation inspect --json.rotation_evidence_result.policy_drift_status`

They are selected claim surfaces for different gates with different admission
predicates.

The critical admission difference is:

- `status --json`
  - approved-target policy drift requires live stable runtime proof
- `rollout rotation inspect --json`
  - approved-target policy drift does not require live stable runtime proof;
    bounded participation evidence may still use the approved target claim
    surface

## Narrow Conclusion

The reproduced mismatch is contractually explainable from repo semantic
surfaces. It is not enough, by itself, to prove a repo-owned contradiction.
