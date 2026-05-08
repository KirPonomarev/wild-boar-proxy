# STEP-19B Metrics Window Report

- Step: `STEP-19B_TWO_WEEK_METRICS_WINDOW_LANE`
- Generated at (UTC): `2026-05-07T05:24:45.087308Z`
- Claim scope: `machine-evidence-only`
- Decision status: `blocked`

## Metrics Evidence Scan Table

| command | exit code | key fact |
|---|---:|---|
| `rg --files | rg -i 'telemetry|metric|metrics|two.?week|2w|14.?day|window'` | 1 | No dedicated telemetry/metrics-window artifact file detected by filename scan. |
| `rg -n --no-heading "\"command\"\s*:\s*\"[^\"]*(telemetry|metric|metrics|two[-_ ]week|2w|14[-_ ]day|window)[^\"]*\"" audit_results/*.json` | 0 | No runtime metrics-window owner command found; only prior scan command references are present. |
| `rg -n --no-heading "two-week|two week|two_week|2w metrics|TWO_WEEK|TWO-WEEK|14-day|14 day|14_day|telemetry|metrics window|metric window" audit_results MASTER_PLAN.md EVIDENCE_CAPTURE_RUNBOOK.md tests wild_boar_proxy` | 0 | Text mentions exist in plan/history, but this is not machine window evidence. |
| `rg -n --no-heading "14-day|14 day|14_day|two-week|two week|two_week|metrics window|window evidence|telemetry window" audit_results MASTER_PLAN.md EVIDENCE_CAPTURE_RUNBOOK.md tests wild_boar_proxy` | 0 | No direct 14-day machine evidence window artifact detected. |

## Blocker Status

| blocker_id | status | reason code | fact |
|---|---|---|---|
| PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING | still_blocked | TWO_WEEK_METRICS_EVIDENCE_WINDOW_INCOMPLETE | A complete 14-day machine metrics window is not evidenced. |
