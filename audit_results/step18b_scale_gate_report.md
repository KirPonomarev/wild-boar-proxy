# STEP-18B Scale Gate Report

- Step: `STEP-18B_SCALE_GATE_AND_TWO_WEEK_METRICS_LANE`
- Generated at (UTC): `2026-05-07T05:10:11.550603Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Command Evidence Table

| command | exit code | tests ran | short fact |
|---|---:|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | 14 | unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step` | 0 | 1 | unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_returns_noop_when_target_is_already_satisfied` | 0 | 1 | unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_existing_stage_20_policy_promotes_one_backend` | 0 | 1 | unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | 1 | unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | 1 | unittest status OK |

## Blocker Mapping

| blocker_id | status | fact |
|---|---|---|
| SCALE_GATE_20_NOT_COMPLETED | still_blocked | Stage_advance_20 unittest contour passed, but canonical scale-gate closure still requires controlled rollout-to-20 evidence per scale criteria. |
| PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING | still_blocked | Two-week metrics evidence remains missing in machine-evidence scan scope. |

## Two-Week Metrics Evidence Scan

| command | exit code | non-empty stdout lines |
|---|---:|---:|
| `rg --files | rg -i 'two.?week|two_week|metrics|metric'` | 1 | 0 |
| `rg -n '\"command\"\s*:\s*\"[^\"]*(two[-_ ]week|metrics)[^\"]*\"' audit_results/*.json` | 1 | 0 |
| `rg -n "two-week|two week|two_week|2w metrics|TWO_WEEK|TWO-WEEK|metrics" audit_results MASTER_PLAN.md EVIDENCE_CAPTURE_RUNBOOK.md tests wild_boar_proxy` | 0 | 21 |

## Residual Blockers

| item | status | reason |
|---|---|---|
| scale gate 20 completion | still_blocked | reason_code=SCALE_GATE_FIELD_PROOF_INSUFFICIENT; unit-test contour pass is not equivalent to canonical controlled rollout proof to 20. |
| two-week metrics evidence | still_blocked | reason_code=TWO_WEEK_METRICS_EVIDENCE_MISSING; no dedicated machine-evidence command/artifact detected. |
