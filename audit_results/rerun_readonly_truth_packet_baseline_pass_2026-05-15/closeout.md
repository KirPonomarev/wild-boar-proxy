# RERUN_READONLY_TRUTH_PACKET_BASELINE_PASS Closeout

## Goal

Repeat the readonly semantic baseline after the `overview` live handoff repair and decide whether the canonical command packets, live GET packets, and 4 core UI live surfaces now agree strongly enough to move into sandbox boundary work.

## Result

- status: completed
- final verdict: GO_TO_SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS
- next action: start the sandbox data-boundary and rollback contour

## Contour Capsule

- goal: rerun the readonly truth baseline on `quick-start`, `overview`, `accounts`, and `api-connections` after the overview live pending-state fix
- branch: `codex/external-agent-lab-isolated`
- head: `Rerun readonly truth packet baseline after overview fix (current contour commit)`
- touched files: `audit_results/rerun_readonly_truth_packet_baseline_pass_2026-05-15/*`
- tests run: `python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/rerun_readonly_truth_packet_baseline_pass_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: Browser Use URL policy still interferes with reloading a deliberate connection-refused page, so this rerun verdict relies on successful readonly truth captures rather than a fresh browser-failure replay
- next exact command: `python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`

## Verification

- tests: pass
- build: not applicable; audit-only contour with no code changes
- manual: canonical packets, live packets, and browser screenshots were captured again and compared across the 4 core screens
- live verification: `overview` now passes both pending and final live phases; `quick-start`, `accounts`, and `api-connections` remain aligned with readonly packets

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/rerun_readonly_truth_packet_baseline_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/rerun_readonly_truth_packet_baseline_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/rerun_readonly_truth_packet_baseline_pass_2026-05-15/mismatch_report.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `Rerun readonly truth packet baseline after overview fix (current contour commit)`
- pushed: pending at artifact generation time

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; only readonly command packets, readonly HTTP packets, screenshots, and audit artifacts were added

## Notes

- blockers encountered: no blocking mismatches remained after the overview handoff repair; the only residual quirk is that broad DOM probes can still read hidden shared shell placeholders on screens where those nodes are not visible truth claims
- follow-up contour: `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`
- resume from here: `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS`
