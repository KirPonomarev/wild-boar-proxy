<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Persistent Custom Profile Backup Rollback Repair R1 Closeout

## Goal

Repair and classify Persistent Custom profile backup/rollback readiness without launching native Codex, deleting persistent history, or treating an incomplete backup as proof.

## Result

- status: ok
- final verdict: WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY
- closure state: CLOSED

## Contour Capsule

- goal: create a packet-backed selective state backup with cache exclusions and rollback readiness for the WBP-owned Persistent Custom profile
- branch: codex/external-agent-lab-isolated
- head: 9af9810e2ce0a286d5e8779657e2c585de5604a2
- touched files: tools/persistent_custom_profile_backup_repair_r1_probe.py; tests/test_native_filesystem_probe.py; audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27/*
- tests run: python3 -m py_compile tools/persistent_custom_profile_backup_repair_r1_probe.py tests/test_native_filesystem_probe.py; python3 -m pytest tests/test_native_filesystem_probe.py -k 'persistent_backup_repair or persistent_custom_backup_rollback'; python3 tools/persistent_custom_profile_backup_repair_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27
- blocked risks: existing incomplete backup root was preserved and not counted; volatile runtime/cache surfaces were excluded and recorded; native launch and history proof were not attempted
- closure state: CLOSED

## Verification

- tests: targeted backup repair tests passed
- build: Python compilation passed for the backup repair probe and native filesystem test module
- manual: latest timestamped backup root has `.wbp_backup_complete`; secret audit is clean; rollback readiness packet is ok
- live verification: not attempted in this contour

## Artifacts

- spec: thread-only R3_5 contour, not stored in repository
- packet: backup_repair_summary_packet.json
- report: rollback_readiness_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: historical dirty audit_results residue and R2 launcher stdout drift remain quarantined and unstaged
- private-data risk reviewed: evidence stores paths, counts, hashes, and classifications only; raw prompt/auth/session bodies are not recorded in repo evidence

## Notes

- blockers encountered: ambient Original Codex protected-surface drift was classified as read-only drift and not treated as backup failure
- resume from here: CLOSED
