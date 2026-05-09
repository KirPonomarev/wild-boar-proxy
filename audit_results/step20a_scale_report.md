# STEP-20A Scale Report

- Step: `STEP-20A_LIVE_SCALE20_EVIDENCE_LANE`
- Generated at (UTC): `2026-05-07T05:40:57.689666Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Required Command Evidence

| command | exit code | tests ran | key fact |
|---|---:|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | 14 | tests_ran=14; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step` | 0 | 1 | tests_ran=1; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | 1 | tests_ran=1; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | 1 | tests_ran=1; unittest OK |

## Scale Gate Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| SCALE_GATE_20_NOT_COMPLETED | still_blocked | SCALE_GATE_FIELD_PROOF_INSUFFICIENT | Required stage_advance_20 unit tests passed, but no machine field proof of controlled rollout completion to 20 was found. |

## Field-Evidence Scan Facts

| command | exit code | key fact |
|---|---:|---|
| `rg -n --no-heading "\"active_count_observed\"\s*:\s*20" audit_results/*.json` | 1 | No `active_count_observed: 20` machine artifact found in `audit_results/*.json`. |
| `rg -n --no-heading "active_count_observed=16|active_target=20|Stage-20 lane evidence ends" audit_results/step17_release_gate_alignment_report.md MASTER_PLAN.md` | 0 | Existing canonical fact remains `active_count_observed=16` with `active_target=20`. |
| `rg -n --no-heading "\"active_target\"\s*:\s*20" audit_results/*.json` | 0 | `active_target: 20` records exist, but this is not a proof of observed active_count=20. |
