# Persistent Custom Profile History Import R1 Closeout

## Goal

Truthfully classify a bounded WBP-backed Persistent Custom profile continuity chain from existing packet-backed evidence, without widening the claim into route proof, UX re-proof, integration parity, or final E2E.

## Result

- status: ok
- final verdict: WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED_WITH_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: import and revalidate the strongest bounded persistent Custom profile continuity chain under explicit storage/state limits
- branch: codex/external-agent-lab-isolated
- head: 8ff1dc6e756fe9e155ea193cfd3aab7d8dd960b8
- touched files: tools/persistent_custom_profile_history_import_r1_probe.py; tests/test_persistent_custom_profile_history_import_r1_probe.py; audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/*
- tests run: python3 -m py_compile tools/persistent_custom_profile_history_import_r1_probe.py tests/test_persistent_custom_profile_history_import_r1_probe.py; python3 -m pytest -q tests/test_persistent_custom_profile_history_import_r1_probe.py; python3 -m pytest -q tests/test_native_filesystem_probe.py -k "persistent_r2c or persistent_storage_r3 or persistent_storage_r4 or persistent_restore_r5"
- blocked risks: storage-level thread-history proof remains unproven; relaunch restoration source remains unproven; durable restoration remains unproven; declared observed Original drift is classified but not clean
- closure state: CLOSED

## Verification

- tests: 3 passed in tests/test_persistent_custom_profile_history_import_r1_probe.py; 25 passed, 227 deselected in targeted tests/test_native_filesystem_probe.py subset
- build: python3 -m py_compile passed
- manual: JSON parse sweep passed for 21/21 packets; top-level packet status sweep reports 21 ok, 0 blocked
- live verification: no new live launch in this contour; imported bounded continuity chain classified from R1/R2/R2B/R2C/R3/R4 evidence

## Artifacts

- spec: none (thread-only post-mainline contour)
- packet: audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/persistent_profile_summary_packet.json
- report: audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27/independent_persistent_profile_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: 8ff1dc6e756fe9e155ea193cfd3aab7d8dd960b8
- pushed: yes

## Scope Check

- unrelated work mixed in: no; historical dirty worktree entries were quarantined and left untouched
- private-data risk reviewed: yes; raw prompt/thread content not recorded; exact-pattern secret scan clean

## Notes

- blockers encountered: independent audit found an identity-comparison bug; fixed by requiring codex_home and user_data_dir consistency across relaunch and adding regression coverage
- resume from here: CLOSED
