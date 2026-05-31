# Persistent Profile And Thread History R1 Closeout

## Goal

Prove bounded persistent Custom Codex profile identity and relaunch/history
continuity truth for the Custom lane, keep role-slot persistence separate from
thread-history claims, and avoid overclaiming runtime dispatch, simultaneous
execution, or Original Codex profile reuse.

## Result

- status: `ok`
- final verdict: `PERSISTENT_PROFILE_AND_THREAD_HISTORY_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify persistent custom-profile identity, relaunch continuity, cleanup boundaries, role-slot reload boundaries, and thread-history limits without treating temp session truth or synthetic storage state as live native history proof
- branch: `codex/external-agent-lab-isolated`
- head: `8a78f9db6a9d7e1d69eb6ae570a822441c546abf`
- touched files: `tools/persistent_profile_and_thread_history_r1_probe.py`, `tests/test_persistent_profile_and_thread_history_r1_probe.py`, `audit_results/persistent_profile_and_thread_history_r1_2026-05-28/*.json`, `audit_results/persistent_profile_and_thread_history_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile tools/persistent_profile_and_thread_history_r1_probe.py tests/test_persistent_profile_and_thread_history_r1_probe.py`; `python3 -m unittest tests.test_persistent_profile_and_thread_history_r1_probe`; `python3 -m unittest tests.test_codex_custom_sessions tests.test_persistent_profile_launcher_dry_run_enforcement_readiness_r2`; `python3 tools/persistent_profile_and_thread_history_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/persistent_profile_and_thread_history_r1_2026-05-28`; `git diff --check`
- blocked risks: live native relaunch was not attempted here; owner-visible thread continuity remains unproven here; storage-level thread-history classification is limited to synthetic owned state under a contour-local probe root; role-slot persistence remains in an owned temp session root and is not linked to persistent custom-profile storage here; ambient Original Codex protected-surface drift was observed during scan capture, but no Original Codex runtime input or write was counted as contour proof
- closure state: CLOSED

## Verification

- tests: `2 passed` in `tests.test_persistent_profile_and_thread_history_r1_probe`; `31 passed` in `tests.test_codex_custom_sessions` plus `tests.test_persistent_profile_launcher_dry_run_enforcement_readiness_r2`
- build: `py_compile` passed for the contour-local probe and focused probe tests
- manual: the contour-local probe wrote `17/17` JSON artifacts with parseable packet bodies; `persistent_profile_identity_packet.json` classified packet-backed profile identity, `role_slot_persistence_packet.json` showed slot bindings survive reload in the owned temp session root, `reload_revalidation_boundary_packet.json` showed prompt admission remains blocked by `SLOT_CATALOG_REVALIDATION_REQUIRED`, and `thread_history_classification_packet.json` kept thread-history semantics bounded to `synthetic_storage_only_with_limits`
- live verification: no live native relaunch or Original Codex profile import was attempted in this contour; continuity claims are therefore bounded to packet-backed profile identity, owned storage scans, and reload classification rather than native runtime proof

## Artifacts

- spec: thread-only contour plan for `PERSISTENT_PROFILE_AND_THREAD_HISTORY_R1`
- packet: `audit_results/persistent_profile_and_thread_history_r1_2026-05-28/persistent_profile_identity_packet.json`
- report: `audit_results/persistent_profile_and_thread_history_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the contour stores bounded packet metadata only, uses contour-local synthetic probe state under the evidence directory, redacts backend/auth state through existing session surfaces, and does not record raw prompt, raw thread body, or Original Codex private state

## Notes

- blockers encountered: the first real edge was semantic rather than mechanical: the initial relaunch packet wording risked reading like profile reuse had been proven through a native relaunch, while the contour had only packet-backed same-identity classification across before/relaunch scans. That wording was tightened so the packet now says `same_profile_identity_classified_across_relaunch` and keeps `live_native_relaunch_attempted=false`. The second edge was a layer-mixing risk between persistent custom-profile continuity and the multi-slot session reload work from the prior contour. Instead of pretending they were already linked, the probe now emits `role_slot_persistence_packet.json` with `session_root_scope=owned_temp_session_root`, and the gap matrix keeps that seam explicitly open. The third edge was overclaim pressure around synthetic state: the contour intentionally writes a bounded thread/session marker set inside a contour-local probe profile so the storage diff machinery has factual input, but `thread_history_classification_packet.json` keeps `thread_history_preserved=false`, `storage_level_thread_history_proven=false`, and `native_thread_history_restoration_proven=false`. One ambient boundary remains visibly blocked: `original_codex_profile_drift_packet.json` captured protected-surface drift in the user’s current Codex environment during scan comparison, so the contour records that drift as a live limit rather than hiding it.
- resume from here: CLOSED
