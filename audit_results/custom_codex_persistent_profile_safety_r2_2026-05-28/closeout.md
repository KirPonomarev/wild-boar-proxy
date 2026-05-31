# Custom Codex Persistent Profile Safety R2 Closeout

## Goal

Classify the persistent Custom Codex profile safety boundary without live destructive cleanup, live restore, UI change, model-grid work, or new thread-history proof.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_PERSISTENT_PROFILE_SAFE_FROM_ORDINARY_CLEANUP
- closure state: CLOSED

## Contour Capsule

- goal: prove ordinary cleanup, restore-target, same-profile owner, backup-marker, and failed-launch safety boundaries for the already persistent Custom Codex profile
- branch: codex/external-agent-lab-isolated
- head: 405852c87520b00f71aa830f92a2845ef5be5220
- touched files: tools/persistent_custom_profile_safety_r2_probe.py; tools/persistent_profile_backup_restore_dry_run_readiness_r4_probe.py; tools/persistent_profile_launcher_contract_readiness_r1_probe.py; tools/persistent_profile_launcher_dry_run_enforcement_readiness_r2_probe.py; tests/test_persistent_custom_profile_safety_r2_probe.py; audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28/*
- tests run: python3 -m py_compile tools/persistent_custom_profile_safety_r2_probe.py tools/persistent_profile_backup_restore_dry_run_readiness_r4_probe.py tools/persistent_profile_launcher_contract_readiness_r1_probe.py tools/persistent_profile_launcher_dry_run_enforcement_readiness_r2_probe.py wild_boar_proxy/persistent_profile_backup_restore_dry_run.py; python3 -m unittest tests.test_persistent_custom_profile_safety_r2_probe; python3 -m unittest tests.test_persistent_custom_profile_safety_r2_probe tests.test_persistent_profile_backup_restore_dry_run_readiness_r4; python3 -m unittest tests.test_persistent_custom_profile_safety_r2_probe tests.test_persistent_profile_backup_restore_dry_run_readiness_r4 tests.test_native_filesystem_probe; python3 -m unittest tests.test_persistent_custom_profile_safety_r2_probe tests.test_persistent_profile_backup_restore_dry_run_readiness_r4 tests.test_native_filesystem_probe tests.test_persistent_profile_launcher_contract_readiness_r1_probe tests.test_persistent_profile_launcher_dry_run_enforcement_readiness_r2; python3 tools/persistent_custom_profile_safety_r2_probe.py; JSON parse sweep for audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28/*.json; python3 tools/check_closeout_resilience.py audit_results/custom_codex_persistent_profile_safety_r2_2026-05-28/closeout.md; git diff --check
- blocked risks: live cleanup execution not performed; live restore execution not performed; explicit lock acquisition not claimed; thread history, auth, final E2E, all-users, and production backup/export/import claims remain false
- closure state: CLOSED

## Verification

- proof packet: persistent_profile_safety_summary_packet.json status ok, final_status CUSTOM_CODEX_PERSISTENT_PROFILE_SAFE_FROM_ORDINARY_CLEANUP
- root safety: persistent_profile_root_safety_packet.json status ok; CODEX_HOME equals persistent root; child profile paths stay under root; original protected surface overlap is false
- cleanup boundary: cleanup_boundary_packet.json status ok; cleanup_attempted false; cleanup_executed false; cleanup_target_is_persistent_profile_root false; explicit owner delete authorization required true
- same-profile lock truth: same_profile_lock_packet.json status ok; one existing Custom profile owner was observed; this is classified as existing owner, not as lock acquisition; same-profile new launch would be blocked
- backup/restore dry-run: backup_restore_dry_run_packet.json status ok; complete marker validated; restore target is persistent profile root; restore_executed false
- failed launch boundary: failed_launch_non_destructive_packet.json status ok; evidence mode is read-only boundary classification; live failed launch was not executed
- false green: false_green_audit.json status ok; findings empty; thread_history_claimed false; auth_proof_claimed false; final_e2e_claimed false
- independent audit: independent_persistent_profile_safety_audit.json status ok; forbidden_true_fields empty; layer_mixing_packets empty

## Artifacts

- packet: persistent_profile_root_safety_packet.json
- packet: cleanup_boundary_packet.json
- packet: same_profile_lock_packet.json
- packet: backup_restore_dry_run_packet.json
- packet: failed_launch_non_destructive_packet.json
- packet: false_green_audit.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- final contour commit: recorded in delivery note
- pushed: recorded in delivery note

## Scope Check

- product runtime behavior changed: no
- UI changed: no
- live restore/delete/cleanup performed: no
- model grid or agent acceleration touched: no
- support evidence tools adjusted: yes, the R1 launcher contract, R2 dry-run enforcement, and R4 backup/restore dry-run readiness sync gates now quarantine non-current dirty work instead of requiring hard-coded historical path lists
- quarantined dirty runtime/product changes present in worktree: yes; not staged or claimed as current-contour implementation
- unrelated dirty work staged: no
- private-data risk reviewed: yes; packets record paths, statuses, hashes, and booleans only; no raw prompt, secret, or thread content is recorded

## Notes

- blockers encountered: initial live proof blocked because an already-open Custom Codex owner was treated as a failure instead of classified as existing owner; this was narrowed to a packet-level classification and still does not claim lock acquisition
- blockers encountered: /tmp/wbp-cdx-wbp-custom-main resolved through a symlink into the persistent profile tmp directory; the root safety packet now records both lexical /tmp path and resolved profile tmp target
- independent auditor note: existing dirty runtime/native/dry-run changes remain outside this contour; this closeout claims only the proof/evidence/test changes listed in the capsule
- resume from here: CLOSED
