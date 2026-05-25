# WBP Native Codex Custom Isolation And Keychain Root Cause And Repair Pass Closeout

## Goal

Localize and repair the Custom-only native launch path so that WBP-launched
`CODEX_CUSTOM_NATIVE_APP` no longer depends on an invalid external launcher
lane, no longer counts real-home launch as admissible truth, and can re-run as
an isolated HOME/CODEX_HOME launch without touching protected default Codex
surfaces or re-triggering the earlier machine-visible keychain/security lane.

## Result

- status: completed
- final verdict: the invalid marked custom launcher was replaced with a repo-owned recognized launcher that adds an isolated desktop lane with a separate Electron user-data dir; a bounded isolated-home live re-check observed a real `Codex` process, kept all protected default Codex surfaces unchanged, and did not reproduce a machine-visible SecurityAgent/Codex keychain signal
- closure state: CLOSED

## Contour Capsule

- goal: close the safety/isolation blocker before any further native routing or usability work by repairing the Custom launch seam and proving the admitted isolated lane does not touch current Codex surfaces
- branch: codex/external-agent-lab-isolated
- head: d0d67825
- touched files: wild_boar_proxy/runtime.py, tests/test_cli.py, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/process_lineage_packet.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/default_surface_drift_localization_packet.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/keychain_risk_localization_packet.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/custom_launch_dependency_packet.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/custom_isolation_repair_packet.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/independent_repair_audit.json, audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_cli.CliTests.test_repo_owned_default_launcher_payload_includes_isolated_desktop_lane tests.test_cli.CliTests.test_launch_smoke_materializes_repo_owned_default_launcher_when_default_path_is_absent tests.test_cli.CliTests.test_status_does_not_treat_invalid_marked_default_launcher_as_provisioned tests.test_cli.CliTests.test_launch_smoke_does_not_overwrite_self_signed_unrecognized_default_launcher_file tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_codex_launch_modes tests.test_repo_hygiene tests.test_closeout_resilience; python3 -m py_compile wild_boar_proxy/runtime.py; python3 -m json.tool audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/*.json; python3 tools/check_closeout_resilience.py audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/closeout.md; git diff --check
- blocked risks: real-home direct launch of `Codex Custom.app` still touched `~/.codex/config.toml` and is therefore forbidden as Custom truth; accessible native window/usability proof remains not complete; routing/session/account/API claims remain out of scope
- closure state: CLOSED

## Verification

- tests: launcher, contract, dispatch, launch-mode, repo hygiene, and closeout resilience tests passed
- build: py_compile passed for wild_boar_proxy/runtime.py
- manual: active launcher marker state, backup launcher marker state, wrapper/app binary chain, and protected-surface comparisons were inspected directly
- live verification: one bounded isolated-home re-check through the repaired repo-owned launcher observed a live `Codex` pid, kept protected default Codex surfaces unchanged, created the isolated Electron user-data dir, and cleaned up successfully; real-home direct launch was observed separately and explicitly excluded from admissible Custom truth because it touched `~/.codex/config.toml`

## Artifacts

- packet: audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/custom_isolation_repair_packet.json
- packet: audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/default_surface_drift_localization_packet.json
- packet: audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/keychain_risk_localization_packet.json
- report: audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/process_lineage_packet.json
- audit: audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence/independent_repair_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this isolation and keychain repair closeout
- pushed: recorded by repository history after this isolation and keychain repair closeout is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets store only redacted launcher paths, status booleans, and bounded runtime observations without exposing auth values

## Notes

- blockers encountered: the originally active `~/.codex-custom-cli/codex-custom-launch.sh` was marker-invalid and not repo-recognized; the direct real-home wrapper launch touched `~/.codex/config.toml`, so only the isolated HOME/CODEX_HOME lane is admissible for Custom truth
- safety boundary earned: repo-owned recognized launcher now carries an explicit isolated desktop lane with `--user-data-dir "$PROFILE_DIR/electron-user-data"` and the bounded isolated re-check preserved all protected default Codex surfaces
- resume from here: CLOSED
