# Custom Codex Persistent Profile Safety R2 Closeout

## Goal

Prove that the persistent Custom Codex profile safety lane is bounded against ordinary cleanup loss, unsafe restore targeting, ambiguous same-profile concurrency, and weak backup-marker truth without widening the result into memory, auth, or final E2E claims.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_PERSISTENT_PROFILE_SAFE_FROM_ORDINARY_CLEANUP
- closure state: CLOSED

## Contour Capsule

- goal: compose and harden packet-backed persistent-profile safety truth for lock/process gate, backup readiness, restore-target safety, and cleanup boundary limits
- branch: codex/external-agent-lab-isolated
- head: 76b232f3b154dfed74e72eab26879bbece77eebc
- touched files: tools/persistent_custom_profile_safety_r2_probe.py; tests/test_persistent_custom_profile_safety_r2_probe.py; tools/persistent_custom_profile_history_r2b_probe.py; tests/test_native_filesystem_probe.py; tools/persistent_profile_backup_restore_dry_run_readiness_r4_probe.py; audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28/*
- tests run: python3 -m py_compile tools/persistent_custom_profile_safety_r2_probe.py tests/test_persistent_custom_profile_safety_r2_probe.py tools/persistent_profile_backup_restore_dry_run_readiness_r4_probe.py tools/persistent_custom_profile_history_r2b_probe.py tests/test_native_filesystem_probe.py; python3 -m unittest tests.test_persistent_custom_profile_safety_r2_probe; python3 -m unittest tests.test_persistent_profile_backup_restore_dry_run_readiness_r4 tests.test_persistent_custom_profile_safety_r2_probe; python3 -m unittest tests.test_native_filesystem_probe tests.test_persistent_profile_backup_restore_dry_run_readiness_r4 tests.test_persistent_custom_profile_safety_r2_probe; python3 tools/persistent_custom_profile_safety_r2_probe.py --evidence-dir audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28; python3 -c "import json, pathlib; root = pathlib.Path('/Volumes/Work/wild-boar-proxy/audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28'); [json.loads(path.read_text(encoding='utf-8')) for path in sorted(root.glob('*.json'))]"; git diff --check
- blocked risks: live cleanup execution and live restore execution intentionally not performed; explicit lock acquisition is not claimed; thread-history, auth, and final-E2E claims remain intentionally false; backup readiness remains source-chain truth validated in this contour, not newly materialized backup execution
- closure state: CLOSED

## Verification

- tests: focused probe tests plus broad native-filesystem regression coverage for same-profile gate, keychain preflight ordering, R4 quarantine compatibility, and safety-summary non-claims
- build: Python compile pass for all changed probe/test files
- manual: none
- live verification: current-repo safety probe run only; no destructive restore, delete, or cleanup execution performed

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: persistent_profile_safety_summary_packet.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: 76b232f3b154dfed74e72eab26879bbece77eebc (pre-closeout base head; final contour commit recorded in delivery note)
- pushed: not performed in this contour

## Scope Check

- unrelated work mixed in: no; historical dirt stayed quarantined and current support-probe touch was declared in packet truth
- private-data risk reviewed: yes; evidence remains hash/path/status only and does not record raw prompt, secret, or thread content

## Notes

- blockers encountered: an independent audit found four material issues in the first draft of the safety probe; the contour narrowed and fixed backup-root authority, zero-count process truth, sync-gate support-file transparency, and backup-marker payload validation before closure
- resume from here: CLOSED
