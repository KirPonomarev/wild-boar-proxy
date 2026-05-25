# WBP Native Codex Custom Authorized Process Window Usability Proof Pass Closeout

## Goal

Use exact in-thread owner authorization to attempt a real `CODEX_CUSTOM_NATIVE_APP`
 live launch, prove process/window/usability for the custom-only slice, run
 cleanup, and verify that current Codex remained untouched.

## Result

- status: completed
- final verdict: live custom dispatch was attempted and process proof was observed, but the contour closed blocked because no accessible native window was proven for the launched pid and the protected default Codex surface changed during the attempt
- closure state: CLOSED

## Contour Capsule

- goal: execute the authorized custom-only live process/window/usability contour and preserve honest machine truth even if the live proof failed
- branch: codex/external-agent-lab-isolated
- head: 46b01e5c
- touched files: audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_dispatch_authorization_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_custom_live_dispatch_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_process_observation_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_window_observation_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_window_usability_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_current_codex_protection_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_cleanup_rollback_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_original_dispatch_deferred_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_dispatch_false_green_audit.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/protected_surface_control_packet.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/custom_live_attempt_receipt.json, audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_native_launch_dispatch tests.test_native_launch_contract tests.test_codex_launch_modes tests.test_repo_hygiene tests.test_closeout_resilience; python3 -m py_compile wild_boar_proxy/native_launch_dispatch.py wild_boar_proxy/native_launch_contract.py; python3 -m wild_boar_proxy status --json; live isolated-home custom launch attempt with machine observation; python3 -m json.tool audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/*.json; python3 tools/check_closeout_resilience.py audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/closeout.md; git diff --check
- blocked risks: launched pid 87999 had no accessible window for honest usability proof; protected surface `default_app_support_codex` changed during the custom launch attempt; owner reported a keychain-reset prompt and machine security logs showed contemporaneous keychain activity, but a machine-only reset prompt proof was not available
- closure state: CLOSED

## Verification

- tests: dispatch, contract, launch-mode, repo hygiene, and closeout resilience test suites passed before the live attempt
- build: py_compile passed for native launch dispatch and contract modules
- manual: active-thread owner authorization, existing Codex process state, custom launcher chain, isolated-home launch harness, and protected-surface control observation were inspected directly
- live verification: authorized custom launch was attempted through an isolated temporary home; process proof succeeded, cleanup succeeded, but window/usability proof and current-Codex untouched proof failed

## Artifacts

- packet: audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_custom_live_dispatch_packet.json
- packet: audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_current_codex_protection_packet.json
- report: audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/native_live_dispatch_false_green_audit.json
- report: audit_results/wbp_native_codex_custom_authorized_process_window_usability_proof_pass_2026-05-25/evidence/independent_live_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this authorized live proof closeout
- pushed: recorded by repository history after this authorized live proof closeout is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; evidence stores only redacted operational truth and does not expose copied auth values or raw temporary paths beyond packet summaries

## Notes

- blockers encountered: the live custom pid was observed, but System Events reported zero accessible windows for that pid while launch logs reported `window ready-to-show`; the protected default Codex surface changed during launch while a 25-second no-launch control remained stable
- resume from here: CLOSED
