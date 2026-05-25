# WBP Native Codex Custom Config Drift Root Cause Pass Closeout

## Goal

Localize the source of the previously observed `~/.codex/config.toml` drift
during repaired isolated Custom launch, using structural config diff, process
timeline, environment classification, `lsof` polling, and protected-surface
snapshots without attempting window/usability, prompt, session, routing,
Original mode, or current config repair.

## Result

- status: completed
- final verdict: blocked; the instrumented launch did not reproduce `~/.codex/config.toml` content drift, no child environment pointed at current `~/.codex`, and `lsof` produced no writer candidates, so the responsible writer remains unknown; the same launch window still changed `default_app_support_codex`, so protected-surface safety remains blocked
- closure state: CLOSED

## Contour Capsule

- goal: identify the writer/source behind current Codex config drift before any further Custom window/usability or routing proof
- branch: codex/external-agent-lab-isolated
- head: 080f2982
- touched files: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/codex_config_structural_diff_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/codex_config_drift_process_timeline_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/custom_launch_env_inheritance_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/active_main_codex_write_risk_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/codex_config_drift_root_cause_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/custom_config_drift_blocked_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/protected_surface_no_launch_control_packet.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/independent_config_drift_audit.json, audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_cli.CliTests.test_repo_owned_default_launcher_payload_includes_isolated_desktop_lane tests.test_native_launch_dispatch tests.test_native_launch_contract tests.test_codex_launch_modes tests.test_repo_hygiene tests.test_closeout_resilience; python3 -m json.tool audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/*.json; python3 tools/check_closeout_resilience.py audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/closeout.md; git diff --check
- blocked risks: responsible writer for the prior `~/.codex/config.toml` drift remains unknown because the drift was not reproduced under instrumentation; kernel-level writer tracing was unavailable without elevated privileges; repaired isolated Custom launch still changed `default_app_support_codex`
- closure state: CLOSED

## Verification

- tests: targeted launcher, native dispatch, native contract, launch-mode, repo hygiene, and closeout resilience suites passed
- build: no code changed in this contour; prior relevant modules remained covered by the targeted tests
- manual: prior reproof packets, current config metadata, available local instrumentation, and macOS writer-attribution tool availability were inspected directly
- live verification: one instrumented repaired isolated Custom launch captured process tree snapshots, classified child env for HOME/CODEX_HOME/WBP_CONFIG_TOML, polled `lsof` for `~/.codex/config.toml`, compared structural config shape before/after, and captured protected-surface snapshots

## Artifacts

- packet: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/codex_config_structural_diff_packet.json
- packet: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/codex_config_drift_process_timeline_packet.json
- packet: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/custom_launch_env_inheritance_packet.json
- packet: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/custom_config_drift_blocked_packet.json
- control: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/protected_surface_no_launch_control_packet.json
- audit: audit_results/wbp_native_codex_custom_config_drift_root_cause_pass_2026-05-25/evidence/independent_config_drift_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this config drift root-cause closeout
- pushed: recorded by repository history after this config drift root-cause closeout is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; structural config diff stores hashes, sizes, mtimes, changed key/section names, and no raw full config or auth values

## Notes

- blockers encountered: `fs_usage` required root and `opensnoop` required additional privileges, so kernel-backed writer attribution was unavailable in this environment; `lsof` polling produced no writer candidates during the bounded launch
- safety boundary: no current `~/.codex/config.toml` repair, restore, rewrite, or normalization was performed
- resume from here: CLOSED
