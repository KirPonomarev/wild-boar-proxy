# Custom Codex Persistent Thread History Proof R5 Closeout

## Goal

Repeat the persistent Custom Codex thread-history relaunch contour with a fresh owner nonce and a corrected proof lane that binds the actual nonce-bearing session surface without recording raw thread content.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_THREAD_HISTORY_PRESERVED_ACROSS_RELAUNCH
- closure state: CLOSED

## Contour Capsule

- goal: prove persistent Custom Codex thread history survives relaunch using owner-visible continuity plus hash/metadata-only selected session target correlation
- branch: codex/external-agent-lab-isolated
- head: 35fed46c8904210c9514cad9855ea00c98497c2e
- touched files: tools/persistent_custom_profile_history_r2b_probe.py; tools/persistent_custom_profile_restoration_correlation_r5_probe.py; tests/test_persistent_custom_profile_history_r3_probe.py; audit_results/custom_codex_persistent_thread_history_proof_r5_2026-05-28/*
- tests run: python3 -m py_compile tools/persistent_custom_profile_history_r2b_probe.py tools/persistent_custom_profile_restoration_correlation_r5_probe.py; python3 -m unittest tests.test_persistent_custom_profile_history_r3_probe; python3 -m unittest tests.test_persistent_custom_profile_history_r3_probe tests.test_native_filesystem_probe; JSON parse sweep on audit_results/custom_codex_persistent_thread_history_proof_r5_2026-05-28/*.json; python3 tools/check_closeout_resilience.py audit_results/custom_codex_persistent_thread_history_proof_r5_2026-05-28/closeout.md; git diff --check
- blocked risks: durable restoration not proven; final E2E not claimed; model availability not claimed; keychain prompt absence not counted as auth success; native UX acceptance not claimed
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_persistent_custom_profile_history_r3_probe tests.test_native_filesystem_probe` passed, 272 tests
- build: `python3 -m py_compile tools/persistent_custom_profile_history_r2b_probe.py tools/persistent_custom_profile_restoration_correlation_r5_probe.py` passed
- manual: owner entered the R5 nonce prompt, then confirmed `done`; after relaunch owner confirmed `вижу`
- live verification: `persistent_custom_profile_history_r2b_summary_packet.json` reports `CUSTOM_CODEX_THREAD_HISTORY_PRESERVED_ACROSS_RELAUNCH`

## Artifacts

- spec: thread instructions and contour-local owner flow in this conversation
- packet: `persistent_custom_profile_history_r2b_summary_packet.json`
- report: this closeout

## Git

- branch: codex/external-agent-lab-isolated
- commit: not committed in this closeout note
- pushed: not pushed in this closeout note

## Scope Check

- unrelated work mixed in: no new broad UI, runtime rollout, model route, auth repair, or Original Codex behavior changes were intentionally added for this R5 proof
- private-data risk reviewed: raw thread content and raw nonce are not recorded in packets; proof uses owner nonce hash plus selected session surface metadata

## Notes

- blockers encountered: R4 failed because stale target selection saw zero selected target changes; R5 corrected target selection and target manifest timing, then corrected relaunch profile-state classification so service runtime churn does not count as selected thread-history loss when selected session targets are retained
- resume from here: CLOSED
