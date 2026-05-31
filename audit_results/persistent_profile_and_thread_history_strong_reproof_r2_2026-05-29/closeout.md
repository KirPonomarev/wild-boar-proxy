# PERSISTENT_PROFILE_AND_THREAD_HISTORY_STRONG_REPROOF_R2 Closeout

## Goal

Strengthen item-5 truth beyond `synthetic_storage_only_with_limits` by
reproving stable persistent profile identity, relaunch continuity, and the
strongest honest thread-history continuity layer on current code, while keeping
storage proof, role-slot persistence, cleanup truth, and Original Codex
isolation separated.

## Result

- status: closed honestly with limits
- final verdict: `PERSISTENT_PROFILE_AND_THREAD_HISTORY_STRENGTHENED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: materially strengthen persistent profile and thread-history truth without upgrading owner-visible continuity into storage-level or local-only restoration proof
- branch: `codex/external-agent-lab-isolated`
- head: `0cc6d700`
- touched files:
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/persistent_profile_identity_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/relaunch_continuity_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/thread_history_restore_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/native_visible_history_boundary_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/role_slot_persistence_relaunch_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/relaunch_fallback_boundary_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/cleanup_boundary_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/original_codex_isolation_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/independent_audit_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/closeout.md`
  - supporting sub-evidence under:
    - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r1_probe`
    - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/real_restore_probe`
    - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r2c_admission`
    - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r5_live`
    - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/stronger_integrity`
- tests run:
  - `python3 -m pytest -q tests/test_persistent_profile_and_thread_history_r1_probe.py tests/test_real_history_restore_proof_r1_probe.py tests/test_persistent_custom_profile_history_r3_probe.py`
  - `python3 -m py_compile tools/persistent_profile_and_thread_history_r1_probe.py tools/real_history_restore_proof_r1_probe.py tools/persistent_custom_profile_r2c_owner_visible_thread_continuity_probe.py tests/test_persistent_profile_and_thread_history_r1_probe.py tests/test_real_history_restore_proof_r1_probe.py tests/test_persistent_custom_profile_history_r3_probe.py`
  - `python3 -m unittest tests.test_persistent_profile_launcher_dry_run_enforcement_readiness_r2 tests.test_persistent_profile_launcher_contract_readiness_r1_probe tests.test_native_filesystem_probe`
  - `python3 -m pytest -q tests/test_stronger_integrity_recheck_r1_probe.py`
  - `python3 tools/persistent_profile_and_thread_history_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r1_probe`
  - `python3 tools/real_history_restore_proof_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/real_restore_probe`
  - `python3 tools/persistent_custom_profile_r2c_owner_visible_thread_continuity_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r2c_admission --execution-mode admission --skip-git`
  - `python3 tools/persistent_custom_profile_restoration_correlation_r5_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r5_live --execution-mode admission --owner-nonce <redacted> --skip-git`
  - `python3 tools/persistent_custom_profile_restoration_correlation_r5_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r5_live --execution-mode first-launch --owner-nonce <redacted> --startup-wait-seconds 12 --skip-git`
  - `python3 tools/persistent_custom_profile_restoration_correlation_r5_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r5_live --execution-mode relaunch --owner-prompt-entered --nonce-used --target-window-clear --evidence-dir-preserved --startup-wait-seconds 12`
  - `python3 tools/persistent_custom_profile_restoration_correlation_r5_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/r5_live --execution-mode classify --owner-relaunch-checked --same-nonce-thread-visible true --target-window-clear --evidence-dir-preserved`
  - `python3 tools/stronger_integrity_recheck_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/stronger_integrity`
  - JSON parse sweep over `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/**/*.json`
- blocked risks:
  - native-visible continuity is now observed, but storage-level thread history still remains unproven
  - local-only restoration source remains unproven
  - role-slot persistence remains bounded to owned temp session scope and is not upgraded into provider/model identity persistence
  - no-hidden-fallback across saved slot provider/model remains unproven
  - cleanup truth remains bounded to non-deletion policy/observation
  - Original Codex isolation remains bounded by unknown drift attribution in current integrity recheck
- closure state: CLOSED

## Verification

- tests:
  - `18 passed` across `tests/test_persistent_profile_and_thread_history_r1_probe.py`, `tests/test_real_history_restore_proof_r1_probe.py`, and `tests/test_persistent_custom_profile_history_r3_probe.py`
  - `282 passed` in `tests.test_persistent_profile_launcher_dry_run_enforcement_readiness_r2`, `tests.test_persistent_profile_launcher_contract_readiness_r1_probe`, and `tests.test_native_filesystem_probe`
  - `3 passed` in `tests/test_stronger_integrity_recheck_r1_probe.py`
- build:
  - `py_compile` passed for the persistent-profile/history probes and focused tests
- manual:
  - `r1_probe` reproduced `synthetic_storage_only_with_limits`
  - `real_restore_probe` reproduced `helper_reload_observed_with_limits`
  - `r5_live` advanced beyond both previous ceilings:
    - `same_profile_id_before_and_relaunch = true`
    - `same_profile_root_before_and_relaunch = true`
    - `custom_process_observed = true` on relaunch
    - `same_nonce_thread_visible = true`
    - `storage_correlation_classified = true`
  - root-level `thread_history_restore_packet.json` classifies:
    - `owner_visible_restore_plus_storage_correlation_with_limits`
    - `stronger_than_synthetic_storage_only = true`
    - `stronger_than_helper_reload_only = true`
  - root-level `native_visible_history_boundary_packet.json` records:
    - `native_visible_restore_observed = true`
    - while keeping `storage_level_thread_history_proven = false`
  - root-level `role_slot_persistence_relaunch_packet.json` keeps slot reload truth separate from thread-history truth and provider/model persistence
  - root-level `original_codex_isolation_reproof_packet.json` keeps current contour non-mutation true while preserving the unknown-drift blocker
- live verification:
  - yes, bounded live owner path was exercised
  - owner entered the nonce-bearing prompt in the launched Persistent Custom window
  - after controlled relaunch, owner confirmed the same nonce thread remained visible
  - raw nonce and raw thread content were not stored in repo evidence

## Artifacts

- spec: thread-only contour plan, not stored in repo by policy
- packet:
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/persistent_profile_identity_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/relaunch_continuity_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/thread_history_restore_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/native_visible_history_boundary_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/role_slot_persistence_relaunch_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/relaunch_fallback_boundary_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/cleanup_boundary_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/original_codex_isolation_reproof_packet.json`
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/independent_audit_packet.json`
- report:
  - `audit_results/persistent_profile_and_thread_history_strong_reproof_r2_2026-05-29/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; existing dirty files outside this contour were left untouched
- private-data risk reviewed: yes; raw nonce, raw prompt text, and raw thread content were not preserved in the contour evidence, and the only discovered raw-nonce launcher log was removed before staging

## Notes

- blockers encountered:
  - the plain item-5 `R1` contour still bottoms out at synthetic storage only
  - the helper-reload contour still bottoms out below native-visible restore
  - the R5 live lane required an owner-ready stop, then an owner-prompt stop, then a relaunch-visibility stop; only after all three were satisfied did the stronger classification materialize
  - storage correlation strengthened, but it still does not prove durable restoration or local-only restoration source
  - the fresh stronger-integrity recheck no longer localized the blocker as ambient-external; on current code it stayed `integrity_remains_blocked_unknown_attribution`, so item-5 strengthening was kept separate from integrity strengthening
- resume from here: CLOSED
