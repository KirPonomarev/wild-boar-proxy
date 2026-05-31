# STRONGER_INTEGRITY_RECHECK_R1 Closeout

## Goal

Strengthen the final E2E integrity limiter as far as safely possible by rerunning protected-surface integrity checks, separating repo dirt from protected Codex drift, and classifying whether the remaining blocker is cleanly attributable.

## Result

- status: ok
- final verdict: STRONGER_INTEGRITY_RECHECK_CLASSIFIED_WITH_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: rerun integrity checks without touching protected Codex surfaces and determine whether the final E2E integrity limiter is reduced or precisely localized.
- branch: codex/external-agent-lab-isolated
- head: 166d0b69
- touched files: tools/stronger_integrity_recheck_r1_probe.py; tests/test_stronger_integrity_recheck_r1_probe.py; audit_results/stronger_integrity_recheck_r1_2026-05-28/*.json; audit_results/stronger_integrity_recheck_r1_2026-05-28/closeout.md
- tests run: python3 -m pytest -q tests/test_stronger_integrity_recheck_r1_probe.py; python3 -m py_compile tools/stronger_integrity_recheck_r1_probe.py tests/test_stronger_integrity_recheck_r1_probe.py; python3 tools/stronger_integrity_recheck_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/stronger_integrity_recheck_r1_2026-05-28; python3 -m pytest -q tests/test_stronger_integrity_recheck_r1_probe.py tests/test_real_history_restore_proof_r1_probe.py tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py; JSON parse sweep; python3 tools/check_closeout_resilience.py --staged-only; git diff --check
- blocked risks: clean stronger integrity was not observed; protected-surface drift remains present but is localized as ambient-external; bundle/hash observation remains scope-only and does not prove full runtime integrity; imported safety was not reproven here
- closure state: CLOSED

## Verification

- tests: 3 passed in the new contour test; 7 passed in the combined focused regression run with history restore and final E2E tests
- build: py_compile passed for the new probe and test
- manual: generated 6/6 JSON packets and parsed all packets successfully
- live verification: live recheck classified the remaining limiter as `integrity_blocker_localized_as_ambient_external`

## Artifacts

- spec: thread-only contour plan
- packet: protected_surface_recheck_packet.json; original_codex_untouched_packet.json; integrity_strengthening_packet.json; integrity_gap_matrix.json; false_green_boundary_packet.json; independent_audit_packet.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: 166d0b69
- pushed: pending at closeout authoring

## Scope Check

- unrelated work mixed in: no; existing dirty worktree entries were left untouched and not staged
- private-data risk reviewed: yes; reads remain inspection-only, auth values are not parsed or recorded, and no protected Codex surface was written

## Notes

- blockers encountered: protected-surface attribution did not strengthen to a clean no-drift pass; instead it localized the blocker as ambient-external and kept full runtime integrity as a non-claim.
- resume from here: CLOSED
