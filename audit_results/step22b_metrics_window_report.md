# STEP-22B Metrics Window Report

- Step: `STEP-22B_PILOT_BLOCKER_AND_METRICS_WINDOW_LANE`
- Generated at (UTC): `2026-05-07T06:00:10Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Pilot Blocker Component Checks

| component | command | exit code | status | fact |
|---|---|---:|---|---|
| installer | `rg -n --no-heading '"command"\s*:\s*"python3 -m unittest -q tests\.test_cli -k installer"' audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | step18a_test_runs contains installer command evidence. |
| legacy_import | `rg -n --no-heading '"command"\s*:\s*"python3 -m unittest -q tests\.test_cli -k legacy_import"' audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | step18a_test_runs contains legacy import command evidence. |
| security | `rg -n --no-heading 'test_diagnostics_export_redacts_runtime_state_and_registry_secrets|test_rollout_evidence_capture_16_redacts_bundle_secrets' audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | step18a_test_runs contains both security command evidences. |
| license | `rg -n --no-heading '"command"\s*:\s*"python3 -m unittest -q tests\.test_cli -k package_experimental"' audit_results/step18a_test_runs.json` | 0 | machine_evidence_found | step18a_test_runs contains package_experimental command evidence. |

## Metrics Evidence Scan Table

| command | exit code | key fact |
|---|---:|---|
| `rg --files audit_results | rg -i 'telemetry|metric|metrics|two.?week|2w|14.?day|window'` | 0 | Only prior metrics artifacts are listed; no complete 14-day window artifact was detected. |
| `rg -n --no-heading '"command"\s*:\s*"[^\"]*(telemetry|metric|metrics|two[-_ ]week|2w|14[-_ ]day|window)[^\"]*"' audit_results/*.json` | 0 | Hits are scan-command mentions, not a complete 14-day runtime window command trail. |
| `rg -n --no-heading '"machine_window_artifact_detected"\s*:\s*false' audit_results/step19b_metrics_capture.json` | 0 | Prior machine assessment records `machine_window_artifact_detected=false`. |
| `rg -n --no-heading '"reason_code"\s*:\s*"TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE"' audit_results/step19b_metrics_capture.json` | 0 | Prior machine assessment keeps reason code `TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE`. |

## Blocker Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING | still_blocked | TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE | A complete 14-day machine metrics window is not evidenced in repo scope. |
