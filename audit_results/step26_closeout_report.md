# STEP-26 Closeout Report

- Generated at (UTC): `2026-05-07T08:06:07Z`
- Claim scope: `machine-evidence-only`
- Overall decision: `blocked`
- Lane A status: `still_blocked` (`SCALE_GATE_FIELD_PROOF_INSUFFICIENT`)
- Lane B status: `still_blocked` (`TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE`)

## FACT_TABLE

| command | exit_code | fact |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | `Ran 14 tests`; `OK`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | `Ran 1 test`; `OK`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | `Ran 1 test`; `OK`. |
| `rg -n --no-heading '"active_count_observed"\s*:\s*20' audit_results/*.json` | 1 | No match in repo scope. |
| `rg -n --no-heading '"operator_approved"\s*:\s*true|"approved_by_operator"\s*:\s*true|"operator_approval"\s*:\s*"approved"' audit_results/*.json` | 1 | No match in repo scope. |
| `rg --files audit_results | rg -i 'telemetry|metric|metrics|two.?week|2w|14.?day|window'` | 0 | Metrics-related files listed. |
| `rg -n --no-heading '"machine_window_artifact_detected"\s*:\s*false' audit_results/step19b_metrics_capture.json` | 0 | Found line 100 with `machine_window_artifact_detected: false`. |
| `rg -n --no-heading '"reason_code"\s*:\s*"TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE"' audit_results/step19b_metrics_capture.json` | 0 | Found line 104 with required reason code. |

## Blocker Facts

- `SCALE_GATE_20_NOT_COMPLETED` remains blocked because repository scans produced no machine proof line for `active_count_observed=20` and no operator-approval marker.
- `PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING` remains blocked because the prior machine capture still records missing 14-day window evidence.

## Internal Consistency Verdict

- `VERDICT: PASS` for artifact internal consistency.
