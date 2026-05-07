# STEP-21A Scale Report

- Step: `STEP-21A_LIVE_SCALE20_EVIDENCE_LANE`
- Generated at (UTC): `2026-05-07T05:50:04Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Required Command Evidence

| command | exit code | tests ran | key fact |
|---|---:|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | 14 | unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step` | 0 | 1 | unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | 1 | unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | 1 | unittest OK |

## Scale Gate Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| SCALE_GATE_20_NOT_COMPLETED | still_blocked | SCALE_GATE_FIELD_PROOF_INSUFFICIENT | Required tests passed; no repo-scope operator-approved live proof for `active_count_observed=20` was found. |

## Field-Evidence Scan Facts

| command | exit code | key fact |
|---|---:|---|
| `rg -n --no-heading "\"active_count_observed\"\s*:\s*20" audit_results/*.json` | 1 | No machine artifact with `active_count_observed: 20` found. |
| `rg -n --no-heading "operator-approved|operator approved|operator_approved|approved_by_operator" audit_results MASTER_PLAN.md EVIDENCE_CAPTURE_RUNBOOK.md EXECUTION_WAVE_1C.md` | 0 | Found plan references only; no operator-approved proof artifact in `audit_results`. |
| `jq '.lanes[] | select(.fixture.source_stage=="15" and .fixture.target_stage=="20") | {lane_stage:(.fixture.source_stage + "->" + .fixture.target_stage), active_count_observed:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.delegated_evidence.pool_count_summary_after_step.active_count_observed), active_target:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.delegated_evidence.pool_count_summary_after_step.active_target), postflight_rotation_status:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.postflight_rotation_status), rollback_readiness_status:(.commands[] | select(.command=="rollout stage advance 20 backend-reserve-advance-stage20-step --json") | .stdout_json.stage_advancement_result.rollback_readiness_status)}' audit_results/step16_owner_surface_capture.json` | 0 | Stage-20 lane snapshot remains `active_count_observed=16`, `active_target=20`, `postflight_rotation_status=available`, `rollback_readiness_status=ready`. |
