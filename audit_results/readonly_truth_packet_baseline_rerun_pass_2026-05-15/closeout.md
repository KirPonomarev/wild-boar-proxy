# READONLY_TRUTH_PACKET_BASELINE_RERUN_PASS Closeout

## Goal

Rerun the readonly baseline with explicit owner/delegated truth discipline and
decide whether sandbox-boundary work is now honestly admissible.

## Result

- status: `GO`
- final verdict: `GO_TO_SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`
- next action: open the sandbox boundary and rollback planning contour

## Contour Capsule

- goal: recapture the readonly baseline after the drift diagnosis, keeping
  `healthcheck --json` as owner runtime truth and `status --json` as delegated
  summary
- branch: `codex/external-agent-lab-isolated`
- head: `75a54b6 Diagnose readonly runtime truth drift`
- touched files:
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/contour.md`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/healthcheck_owner_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/status_delegated_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/mode_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/accounts_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/rollout_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/external_models_readonly_packets.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/baseline_summary.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/coherence_matrix.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/decision_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/independent_audit.md`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_status_reloads_reconciled_state_after_healthcheck tests.test_cli.CliTests.test_healthcheck_returns_attestation tests.test_cli.CliTests.test_status_does_not_greenwash_failed_attestation tests.test_ui_shell`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - none material inside the rerun contour
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - targeted runtime-truth CLI tests passed
  - `tests.test_ui_shell` passed
- build:
  - `git diff --check`
- manual:
  - owner packet was captured before delegated packet
  - semantic coherence held across owner/delegated runtime fields
  - mode packet matched runtime mode
  - accounts counts matched status pool summary
  - rollout remained supporting warning evidence only
  - external-models remained supporting readonly evidence only
- live verification:
  - yes; direct readonly runtime packets were executed live without mutation

## Artifacts

- spec:
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/contour.md`
- packet:
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/healthcheck_owner_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/status_delegated_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/mode_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/accounts_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/rollout_packet.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/external_models_readonly_packets.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/baseline_summary.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/coherence_matrix.json`
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/decision_packet.json`
- report:
  - `audit_results/readonly_truth_packet_baseline_rerun_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; readonly packets were observed, no mutation
  surface executed`

## Notes

- blockers encountered:
  - none material after rerun discipline was applied
- follow-up contour:
  - `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`
- resume from here: `prepare sandbox boundary and rollback plan on top of the now-stable readonly baseline`
