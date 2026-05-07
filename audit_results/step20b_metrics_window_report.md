# STEP-20B Metrics Window Report

- Step: `STEP-20B_PILOT_BLOCKER_AND_METRICS_WINDOW_LANE`
- Generated at (UTC): `2026-05-07T05:40:57.689666Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Pilot Blocker Component Checks

| component | command | exit code | status | fact |
|---|---|---:|---|---|
| installer | `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k installer\"" audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | 28:      "command": "python3 -m unittest -q tests.test_cli -k installer", |
| legacy_import | `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k legacy_import\"" audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | 38:      "command": "python3 -m unittest -q tests.test_cli -k legacy_import", |
| security | `rg -n --no-heading "test_diagnostics_export_redacts_runtime_state_and_registry_secrets|test_rollout_evidence_capture_16_redacts_bundle_secrets" audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | 58:      "command": "python3 -m unittest -q tests.test_cli.CliTests.test_diagnostics_export_redacts_runtime_state_and_registry_secrets", |
| license | `rg -n --no-heading "\"command\"\s*:\s*\"python3 -m unittest -q tests\.test_cli -k package_experimental\"" audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | 48:      "command": "python3 -m unittest -q tests.test_cli -k package_experimental", |
| license_criterion_text_presence | `rg -n --no-heading "minimum license note" MASTER_PLAN.md audit_results/step17_fact_dump.json` | 0 | text_reference_found | audit_results/step17_fact_dump.json:68:      "Pilot gate includes installer, legacy import, minimum security, minimum license note, and two-week metrics.", |

## Metrics Evidence Scan Table

| command | exit code | key fact |
|---|---:|---|
| `rg --files audit_results | rg -i "telemetry|metric|metrics|two.?week|2w|14.?day|window"` | 0 | audit_results/step19b_metrics_window_report.md |
| `rg -n --no-heading "\"command\"\s*:\s*\"[^\"]*(telemetry|metric|metrics|two[-_ ]week|2w|14[-_ ]day|window)[^\"]*\"" audit_results/*.json` | 0 | audit_results/step18b_owner_surface_capture.json:96:        "command": "rg --files | rg -i 'two.?week|two_week|metrics|metric'", |
| `rg -n --no-heading "\"machine_window_artifact_detected\"\s*:\s*false" audit_results/step19b_metrics_capture.json` | 0 | 100:    "machine_window_artifact_detected": false, |
| `rg -n --no-heading "\"reason_code\"\s*:\s*\"TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE\"" audit_results/step19b_metrics_capture.json` | 0 | 104:    "reason_code": "TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE" |

## Blocker Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING | still_blocked | TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE | A complete 14-day machine metrics window is not evidenced. |
