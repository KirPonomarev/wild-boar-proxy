# STEP-22A Scale Report

- Step: `STEP-22A_LIVE_SCALE20_EVIDENCE_LANE`
- Generated at (UTC): `2026-05-07T06:00:10Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Blocker Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| SCALE_GATE_20_NOT_COMPLETED | still_blocked | SCALE_GATE_FIELD_PROOF_INSUFFICIENT | Required tests passed and readiness fields are present, but no repo-scope machine artifact proves `active_count_observed=20` with operator-approved live proof. |

## Evidence Table

| command | exit_code | key fact |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | tests_ran=14; unittest OK. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step` | 0 | tests_ran=1; unittest OK. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | tests_ran=1; unittest OK. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | tests_ran=1; unittest OK. |
| `rg -n --no-heading '"active_count_observed"\s*:\s*20' audit_results/*.json` | 1 | No JSON artifact with `active_count_observed=20` detected in `audit_results`. |
| `rg -n --no-heading '"operator_approved"\s*:\s*true|"approved_by_operator"\s*:\s*true|"operator_approval"\s*:\s*"approved"' audit_results/*.json` | 1 | No positive operator-approval field detected in JSON artifacts. |
| `jq '.lanes[] | select(.fixture.source_stage=="15" and .fixture.target_stage=="20") | {lane_stage:(.fixture.source_stage + "->" + .fixture.target_stage), active_count_observed:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.delegated_evidence.pool_count_summary_after_step.active_count_observed), active_target:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.delegated_evidence.pool_count_summary_after_step.active_target), postflight_rotation_status:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.postflight_rotation_status), rollback_readiness_status:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.rollback_readiness_status)}' audit_results/step16_owner_surface_capture.json` | 0 | Snapshot reports `active_count_observed=16`, `active_target=20`, `postflight_rotation_status=available`, `rollback_readiness_status=ready`. |
| `jq '.lanes[] | select(.fixture.source_stage=="15" and .fixture.target_stage=="20") | (.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.delegated_evidence.postflight_summary.readiness_summary)' audit_results/step16_owner_surface_capture.json` | 0 | Readiness summary reports `status=ready` with reason `bounded_fallback_and_recovery_contracts_ready`. |

