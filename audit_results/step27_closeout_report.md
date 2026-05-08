# STEP-27 Closeout Report

- Generated at (UTC): `2026-05-07T08:13:42Z`
- Claim scope: `machine-evidence-only`
- Overall decision: `blocked`
- Lane A status: `still_blocked` (`SCALE_GATE_FIELD_PROOF_INSUFFICIENT`)
- Lane B status: `still_blocked` (`TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE`)

## FACT_TABLE

| command | exit_code | key_output |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli -k stage_advance_20` | 0 | `Ran 14 tests in 8.985s`; `OK`; emitted `sync-advance-stage20-inline-auth`, `sync-advance-stage20-contradicted`, `sync-advance-stage20-stable-auth-failure`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_fails_on_postflight_contradiction_after_promotion` | 0 | `Ran 1 test in 1.223s`; `OK`; emitted `sync-advance-stage20-contradicted`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_20_rolls_back_failed_stable_auth_materialization` | 0 | `Ran 1 test in 1.236s`; `OK`; emitted `sync-advance-stage20-stable-auth-failure`. |
| `rg -n --no-heading '"active_count_observed"\s*:\s*20' audit_results/*.json` | 1 | no matches. |
| `rg -n --no-heading '"operator_approved"\s*:\s*true|"approved_by_operator"\s*:\s*true|"operator_approval"\s*:\s*"approved"' audit_results/*.json` | 1 | no matches. |
| `rg --files audit_results | rg -i 'telemetry|metric|metrics|two.?week|2w|14.?day|window'` | 0 | listed: step24b/23b/25b/20b/21b/19b metrics-window reports, `step26b_metrics_window_capture.json`, `step22b_metrics_window_report.md`, `step19b_metrics_capture.json`. |
| `rg -n --no-heading '"machine_window_artifact_detected"\s*:\s*false' audit_results/step19b_metrics_capture.json` | 0 | `100:    "machine_window_artifact_detected": false,` |
| `rg -n --no-heading '"reason_code"\s*:\s*"TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE"' audit_results/step19b_metrics_capture.json` | 0 | `104:    "reason_code": "TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE"` |

## Blocker Facts

- `SCALE_GATE_20_NOT_COMPLETED` remains unresolved: required stage-20 tests pass, but repo-scope machine proof for `active_count_observed=20` plus operator approval is absent.
- `PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING` remains unresolved: machine evidence still marks 14-day metrics window artifact as incomplete (`machine_window_artifact_detected=false`).

## Internal Consistency Verdict

- `VERDICT: PASS` for internal consistency; decision remains `blocked` because unresolved blockers remain.
