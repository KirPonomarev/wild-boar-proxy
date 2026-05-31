# REAL_HISTORY_RESTORE_PROOF_R1 Closeout

## Goal

Strengthen the final E2E history limiter from synthetic storage-only proof to the strongest safely observed restore layer, while keeping history continuity separate from role-slot persistence and native visible restore.

## Result

- status: ok
- final verdict: REAL_HISTORY_RESTORE_CLASSIFIED_WITH_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: prove the strongest observed Custom Codex history restore truth without inflating helper reload into native visible restore.
- branch: codex/external-agent-lab-isolated
- head: ce45ab07
- touched files: tools/real_history_restore_proof_r1_probe.py; tests/test_real_history_restore_proof_r1_probe.py; audit_results/real_history_restore_proof_r1_2026-05-28/*.json; audit_results/real_history_restore_proof_r1_2026-05-28/closeout.md
- tests run: python3 -m pytest -q tests/test_real_history_restore_proof_r1_probe.py; python3 -m py_compile tools/real_history_restore_proof_r1_probe.py tests/test_real_history_restore_proof_r1_probe.py; python3 -m pytest -q tests/test_real_history_restore_proof_r1_probe.py tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py tests/test_persistent_profile_and_thread_history_r1_probe.py; JSON parse sweep; python3 tools/check_closeout_resilience.py --staged-only; git diff --check
- blocked risks: native/user-visible app relaunch restore remains unobserved and non-claim; helper-level reload is not native visible restore; role-slot reload remains separate from thread history; Original Codex profile does not participate in this proof
- closure state: CLOSED

## Verification

- tests: 2 passed for the new contour test; 6 passed in combined focused run with final E2E and persistent profile/history tests
- build: py_compile passed for the new probe and test
- manual: generated 7/7 JSON packets and parsed all packets successfully
- live verification: no native app relaunch was attempted; this contour intentionally stops at helper-level reload continuity

## Artifacts

- spec: thread-only contour plan
- packet: history_restore_packet.json; profile_relaunch_continuity_packet.json; history_vs_slot_separation_packet.json; native_visible_restore_boundary_packet.json; history_restore_gap_matrix.json; false_green_boundary_packet.json; independent_audit_packet.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: ce45ab07
- pushed: pending at closeout authoring

## Scope Check

- unrelated work mixed in: no; existing dirty worktree entries were ignored and not staged
- private-data risk reviewed: yes; raw prompts, raw thread content, auth values, and Original Codex profile contents are not recorded

## Notes

- blockers encountered: native visible restore was not directly observed, so it remains open with limits.
- resume from here: CLOSED
