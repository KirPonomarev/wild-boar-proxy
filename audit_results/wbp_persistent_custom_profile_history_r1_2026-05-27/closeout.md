<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Persistent Custom Profile History R1 Closeout

## Goal

Add and verify the first packet-backed Persistent Custom profile-history contour layer: stable profile identity, deterministic launcher selection, non-destructive cleanup policy, concurrent launch policy, backup/rollback expectation, state-diff classification, and false-green audit.

## Result

- status: blocked
- final verdict: WBP_CUSTOM_PERSISTENT_PROFILE_BLOCKED_LIVE_NOT_ATTEMPTED
- closure state: CLOSED

## Contour Capsule

- goal: classify Persistent Custom profile-history admission and inspection evidence without launching native Codex or claiming thread persistence
- branch: codex/external-agent-lab-isolated
- head: e4215b7de2f05efd216e33d879c9902dd84a817b
- touched files: wild_boar_proxy/native_filesystem_probe.py; tools/persistent_custom_profile_history_r1_probe.py; tests/test_native_filesystem_probe.py; audit_results/wbp_persistent_custom_profile_history_r1_2026-05-27/*
- tests run: python3 -m py_compile wild_boar_proxy/native_filesystem_probe.py tools/persistent_custom_profile_history_r1_probe.py; python3 -m pytest tests/test_native_filesystem_probe.py -k 'persistent_custom or persistent_profile'; python3 tools/persistent_custom_profile_history_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/wbp_persistent_custom_profile_history_r1_2026-05-27
- blocked risks: native launch not attempted; owner thread not created; storage diff absent; thread history preservation not claimed
- closure state: CLOSED

## Verification

- tests: targeted persistent profile tests passed
- build: Python compilation passed for the native filesystem module and R1 probe
- manual: evidence packets show persistent profile root did not exist and no persistent write was performed during inspection
- live verification: not attempted in this contour

## Artifacts

- spec: thread-only R3_5 contour, not stored in repository
- packet: persistent_custom_profile_history_summary_packet.json
- report: independent_persistent_profile_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: historical dirty audit_results residue remains quarantined and unstaged
- private-data risk reviewed: evidence records paths, hashes, sizes, and classifications only; raw prompts/auth/session bodies are not recorded

## Notes

- blockers encountered: live native persistent launch and relaunch were intentionally not attempted in this inspection layer
- resume from here: CLOSED
