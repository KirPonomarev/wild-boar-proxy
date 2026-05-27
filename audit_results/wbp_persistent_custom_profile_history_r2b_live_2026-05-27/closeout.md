# WBP Persistent Custom Profile History R2B Live Relaunch Closeout

## Goal

Classify whether the WBP-backed Persistent Custom Codex profile preserves profile state and thread-history evidence across owner-assisted native relaunch, using the repaired timestamped rollback evidence and without relying on Original Codex profile state.

## Result

- status: blocked
- final verdict: WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN
- closure state: CLOSED

## Contour Capsule

- goal: Run R2B owner-assisted Persistent Custom native relaunch with rollback-reference import, bounded profile manifests, owner nonce boundary, and no false substitution across profile state, thread history, route, egress, model, UX, or Original Codex layers.
- branch: codex/external-agent-lab-isolated
- head: 29aea2755c908e854f3ae439260f98c2bd645651
- touched files: tools/persistent_custom_profile_history_r2b_probe.py; tests/test_native_filesystem_probe.py; audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/*
- tests run: python3 -m pytest tests/test_native_filesystem_probe.py tests/test_repo_hygiene.py tests/test_closeout_resilience.py -q; python3 tools/persistent_custom_profile_history_r2b_probe.py --execution-mode admission; python3 tools/persistent_custom_profile_history_r2b_probe.py --execution-mode first-launch with hash-only owner nonce packet; python3 tools/persistent_custom_profile_history_r2b_probe.py --execution-mode relaunch-classify --owner-ready-now --prompt-entered --nonce-used --evidence-dir-preserved --owner-visible-prior-thread unknown
- blocked risks: Persistent Custom process launched and relaunched, owner marker was recorded, rollback reference was ready, but bounded relaunch evidence did not prove profile-state preservation and did not prove thread-history preservation; no direct egress, model availability, native UX acceptance, Keychain independence, Original reversibility, or final E2E claim was made.
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_native_filesystem_probe.py tests/test_repo_hygiene.py tests/test_closeout_resilience.py -q` reported `230 passed`.
- build: `python3 -m py_compile tools/persistent_custom_profile_history_r2b_probe.py` passed during development.
- manual: owner provided `owner_ready_now=true; prompt_entered=true; nonce_used=true; evidence_dir_preserved=true` after entering the nonce prompt in the opened Persistent Custom Codex window.
- live verification: `persistent_r2b_relaunch_packet.json` recorded `custom_process_observed=true`; `r2b_owner_action_boundary_packet.json` recorded all owner marker booleans as true; `persistent_r2b_profile_state_preservation_packet.json` recorded `profile_state_preserved=false`; `persistent_r2b_thread_history_preservation_packet.json` recorded `thread_history_preserved=false`.

## Artifacts

- spec: thread-only R2B contour plan; no repo-resident forward roadmap was written.
- packet: `persistent_custom_profile_history_r2b_summary_packet.json`
- report: this closeout and the JSON packets in this evidence directory.

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; historical dirty evidence outside this contour remained unstaged and quarantined.
- private-data risk reviewed: yes; owner nonce and prompt are hash-only in packets, raw prompt/session/auth contents were not recorded by R2B packets.

## Notes

- blockers encountered: Independent audit found that relaunch classification could run side effects before a complete owner marker and that rollback marker binding was too weak. Both defects were fixed and covered by regression tests before live classification continued.
- resume from here: CLOSED
