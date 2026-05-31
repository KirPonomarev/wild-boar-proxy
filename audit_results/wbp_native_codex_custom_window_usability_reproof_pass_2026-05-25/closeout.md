# WBP Native Codex Custom Window Usability Reproof Pass Closeout

## Goal

Re-run the Custom-only Phase 3 process/window/usability proof after the
isolation repair, using only the repaired repo-owned launcher under isolated
HOME/CODEX_HOME, and preserve machine truth without prompt, session, routing,
Original, UI, or final-completion claims.

## Result

- status: completed
- final verdict: blocked after live attempt; the repaired isolated launch produced observable native `Codex` processes and cleanup completed, but pid-bound native window proof was not available and protected default Codex config changed during the launch window
- closure state: CLOSED

## Contour Capsule

- goal: prove or honestly block the repaired Custom native process/window/usability slice without touching current Codex or upgrading the claim into prompt/session/routing
- branch: codex/external-agent-lab-isolated
- head: 32ed7a16
- touched files: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_window_reproof_authorization_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_custom_repaired_dispatch_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_process_observation_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_window_observation_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_window_usability_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_current_codex_protection_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_cleanup_rollback_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_window_reproof_false_green_audit.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_window_reproof_blocked_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/protected_surface_no_launch_control_packet.json, audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_cli.CliTests.test_repo_owned_default_launcher_payload_includes_isolated_desktop_lane tests.test_native_launch_dispatch tests.test_native_launch_contract tests.test_codex_launch_modes; python3 -m py_compile wild_boar_proxy/runtime.py wild_boar_proxy/native_launch_dispatch.py wild_boar_proxy/native_launch_contract.py; live repaired isolated Custom launch; 20-second no-launch protected-surface control; python3 -m json.tool audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/*.json; python3 tools/check_closeout_resilience.py audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/closeout.md; git diff --check
- blocked risks: System Events did not provide pid-bound native window proof for the launched process group; `codex_config` changed during the live launch window; the no-launch control stayed stable, so the drift was not accepted as ambient proof of safety
- closure state: CLOSED

## Verification

- tests: targeted launcher, native dispatch, native contract, and launch-mode suites passed before live proof
- build: py_compile passed for runtime, native launch dispatch, and native launch contract modules
- manual: two read-only explorer audits inspected pid-bound window proof surfaces and native packet false-green guards; their findings were used as audit context only
- live verification: repaired isolated Custom launch ran under temporary HOME/CODEX_HOME, observed a process group rooted at pid 98705, attempted AX/System Events window observation for each launch-process-group pid, cleaned up the process group, and captured before/after protected-surface comparisons

## Artifacts

- packet: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_custom_repaired_dispatch_packet.json
- packet: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_process_observation_packet.json
- packet: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_window_observation_packet.json
- packet: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_repaired_current_codex_protection_packet.json
- packet: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/protected_surface_no_launch_control_packet.json
- audit: audit_results/wbp_native_codex_custom_window_usability_reproof_pass_2026-05-25/evidence/native_window_reproof_false_green_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this window usability reproof closeout
- pushed: recorded by repository history after this window usability reproof closeout is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; evidence records process ids, bounded paths, booleans, and protected-surface comparison metadata without exposing auth values

## Notes

- blockers encountered: process proof succeeded, but AX/System Events returned no pid-bound window for the launched process group; protected-surface comparison showed `codex_config` changed during live launch, while a subsequent 20-second no-launch control stayed unchanged
- false-green boundary: prompt/session/routing were not attempted, web workbench evidence was not substituted, screenshots were not used as primary proof, and native completion was not claimed
- resume from here: CLOSED
