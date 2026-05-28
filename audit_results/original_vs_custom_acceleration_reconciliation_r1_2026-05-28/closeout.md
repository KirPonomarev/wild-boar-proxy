# ORIGINAL_VS_CUSTOM_ACCELERATION_RECONCILIATION_R1 Closeout

## Goal

Strengthen the previously classified acceleration contour as far as safely possible by checking whether any bounded Original Codex vs Custom Codex acceleration comparison is honestly admissible, while keeping timing truth separate from quality claims and broad product-speed language.

## Result

- status: ok
- final verdict: ORIGINAL_VS_CUSTOM_ACCELERATION_RECONCILIATION_CLASSIFIED_WITH_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: classify whether current evidence supports any materially comparable Original vs Custom acceleration claim and localize the blocker if it does not.
- branch: codex/external-agent-lab-isolated
- head: b949362a
- touched files: tools/original_vs_custom_acceleration_reconciliation_r1_probe.py; tests/test_original_vs_custom_acceleration_reconciliation_r1_probe.py; audit_results/original_vs_custom_acceleration_reconciliation_r1_2026-05-28/*.json; audit_results/original_vs_custom_acceleration_reconciliation_r1_2026-05-28/closeout.md
- tests run: python3 -m pytest -q tests/test_original_vs_custom_acceleration_reconciliation_r1_probe.py; python3 -m py_compile tools/original_vs_custom_acceleration_reconciliation_r1_probe.py tests/test_original_vs_custom_acceleration_reconciliation_r1_probe.py; python3 tools/original_vs_custom_acceleration_reconciliation_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/original_vs_custom_acceleration_reconciliation_r1_2026-05-28; python3 -m pytest -q tests/test_original_vs_custom_acceleration_reconciliation_r1_probe.py tests/test_acceleration_and_throughput_classification_r1_probe.py tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py; JSON parse sweep; python3 tools/check_closeout_resilience.py --staged-only; git diff --check
- blocked risks: Original-side timing/request/token measurement surface remains unobserved in admitted inputs; same-binary is scope-observed only and not proven for measured paths; execution-path equivalence remains unknown_or_divergent; bounded custom-side timing remains contour-local only and does not prove product-wide speed gain
- closure state: CLOSED

## Verification

- tests: 2 passed in the new contour test; 6 passed in the combined focused regression run with prior acceleration and final E2E tests
- build: py_compile passed for the new probe and test
- manual: generated 7/7 JSON packets and parsed all packets successfully
- live verification: no live Original-vs-Custom timing benchmark was admitted; the contour instead localized the blocker as missing Original-side measurement plus unmatched measured paths

## Artifacts

- spec: thread-only contour plan
- packet: original_vs_custom_comparability_packet.json; acceleration_measurement_packet.json; acceleration_classification_packet.json; acceleration_non_claims_packet.json; acceleration_gap_matrix.json; false_green_boundary_packet.json; independent_audit_packet.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: b949362a
- pushed: pending at closeout authoring

## Scope Check

- unrelated work mixed in: no; existing dirty worktree entries were left untouched and not staged
- private-data risk reviewed: yes; no auth values, raw prompts, or user thread contents were recorded

## Notes

- blockers encountered: this contour did not produce a clean acceleration comparison; it refined the blocker from generic mixed-surface non-admission to the narrower fact that Original-side measurement is absent while Custom-side timing remains contour-local only.
- resume from here: CLOSED
