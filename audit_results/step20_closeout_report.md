# STEP-20 Closeout Report

- Generated at (UTC): `2026-05-07T05:40:57.689666Z`
- Claim scope: `machine-evidence-only`
- Overall decision: `blocked`
- Lane A status: `still_blocked` (`SCALE_GATE_FIELD_PROOF_INSUFFICIENT`)
- Lane B status: `still_blocked` (`TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE`)

## FACT_TABLE

| command | exit_code | fact |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | tests_ran=14; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_from_stage_15_updates_policy_one_step` | 0 | tests_ran=1; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | tests_ran=1; unittest OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | tests_ran=1; unittest OK |
| `rg -n --no-heading "\"active_count_observed\"\s*:\s*20" audit_results/*.json` | 1 | No active_count_observed=20 match in audit_results JSON scan. |
| `rg -n --no-heading "active_count_observed=16|active_target=20|Stage-20 lane evidence ends" audit_results/step17_release_gate_alignment_report.md MASTER_PLAN.md` | 0 | Prior canonical field fact remains at active_count_observed=16 and active_target=20. |
| `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k installer\"" audit_results/step18a_test_runs.json` | 0 | Installer machine-evidence command is present in step18a_test_runs. |
| `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k legacy_import\"" audit_results/step18a_test_runs.json` | 0 | Legacy import machine-evidence command is present in step18a_test_runs. |
| `rg -n --no-heading "test_diagnostics_export_redacts_runtime_state_and_registry_secrets|test_rollout_evidence_capture_16_redacts_bundle_secrets" audit_results/step18a_test_runs.json` | 0 | Security machine-evidence commands are present in step18a_test_runs. |
| `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k package_experimental\"" audit_results/step18a_test_runs.json` | 0 | Package experimental machine-evidence command is present in step18a_test_runs. |
| `rg --files audit_results | rg -i "telemetry|metric|metrics|two.?week|2w|14.?day|window"` | 0 | Metrics-related filenames in audit_results are limited to prior step19b report/capture artifacts. |
| `rg -n --no-heading "\"command\"\s*:\s*\"[^\"]*(telemetry|metric|metrics|two[-_ ]week|2w|14[-_ ]day|window)[^\"]*\"" audit_results/*.json` | 0 | Metrics keyword command hits are scan-command records in prior artifacts, not a 14-day runtime window proof. |
| `rg -n --no-heading "\"machine_window_artifact_detected\"\s*:\s*false" audit_results/step19b_metrics_capture.json` | 0 | Prior machine assessment explicitly records machine_window_artifact_detected=false. |
| `rg -n --no-heading "\"reason_code\"\s*:\s*\"TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE\"" audit_results/step19b_metrics_capture.json` | 0 | Prior machine assessment keeps reason_code TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE. |

## Blockers Summary

- Open blockers: 2 (`SCALE_GATE_20_NOT_COMPLETED`, `PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING`)
- Closed blockers in step20 scope: 0
- Lane B partial coverage fact: installer/legacy import/security/license command signals are present in prior machine artifacts; overall blocker remains `still_blocked` because 14-day metrics window evidence is incomplete.
