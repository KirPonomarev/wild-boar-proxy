# WBP Native Codex Custom Protected Surface Isolation Repair Pass Closeout

## Goal

Repair and prove the Custom native desktop launch safety seam so it does not
touch current Codex protected surfaces, while treating any macOS Keychain reset
prompt as a hard blocker.

## Result

- status: completed
- final verdict: blocked; the repaired launcher isolated the current Codex
  protected filesystem surfaces during bounded live proof, but the native
  Codex process triggered a macOS `SecurityAgent` window named
  `Связка ключей не найдена`, so Phase 3 remains blocked
- closure state: CLOSED

## Contour Capsule

- goal: prevent Custom native launch from mutating current Codex protected
  surfaces and verify the Keychain prompt boundary before resuming native
  window/usability proof
- branch: codex/external-agent-lab-isolated
- head: 25ab47ff
- touched files: wild_boar_proxy/runtime.py, wild_boar_proxy/native_launch_contract.py, wild_boar_proxy/native_launch_dispatch.py, native_launch_contract.json, native_launch_packet_schema.json, tests/test_cli.py, tests/test_native_launch_contract.py, tests/test_native_launch_dispatch.py, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/custom_profile_safety_before_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/custom_launch_env_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/custom_profile_path_resolution_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/protected_surface_diff_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/keychain_prompt_observation_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/keychain_prompt_refined_observation_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/custom_profile_isolation_repair_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/cleanup_reversibility_packet.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/secret_redaction_audit.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/independent_profile_safety_audit.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/agent_orchestration_audit.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/final_safety_repair_summary.json, audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_cli.CliTests.test_repo_owned_default_launcher_payload_includes_isolated_desktop_lane tests.test_cli.CliTests.test_launch_smoke_materializes_repo_owned_default_launcher_when_default_path_is_absent tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_codex_launch_modes tests.test_repo_hygiene tests.test_closeout_resilience
- blocked risks: `SecurityAgent` Keychain window appeared during isolated
  native Codex desktop launch; no prompt, route, native usability, Original via
  WBP, or final E2E claim is allowed
- closure state: CLOSED

## Verification

- tests: targeted native contract, native dispatch, launcher payload, launch
  client env hygiene, launch modes, repo hygiene, and closeout resilience suites
  passed
- build: no separate build command was required for this Python/package slice
- manual: static launcher/profile path construction was inspected directly and
  by a read-only scanner agent; the worker patch was not accepted blindly and
  was integrated only after local diff/test verification
- live verification: two bounded native Codex desktop safety attempts used a
  temp `WBP_PROFILE_DIR`, fake temp-only auth, protected-surface before/after
  snapshots, process matching by temp profile path, safe cleanup, and
  no-destructive-click Keychain observation

## Artifacts

- packet: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/protected_surface_diff_packet.json
- packet: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/keychain_prompt_refined_observation_packet.json
- packet: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/custom_profile_isolation_repair_packet.json
- packet: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/cleanup_reversibility_packet.json
- audit: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/independent_profile_safety_audit.json
- audit: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/agent_orchestration_audit.json
- summary: audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence/final_safety_repair_summary.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this protected-surface
  isolation repair closeout
- pushed: recorded by repository history after this closeout is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; evidence records path labels, booleans,
  process/window names, and hashes only, with no raw auth token or API key

## Notes

- repaired: repo-owned desktop launcher now uses `WBP_PROFILE_DIR` when present,
  exports isolated `HOME`, `CODEX_HOME`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`,
  and `TMPDIR`, and creates isolated app-support/cache/httpstorage/runtime dirs
- guarded: native Custom contract and dispatch now require app-support, cache,
  runtime, and Keychain blocker fields instead of treating generic profile
  isolation as sufficient
- blocker: setting isolated `HOME` prevents current Codex protected surface
  mutation in this proof but causes macOS SecurityAgent to report the keychain
  is missing
- residual risk: directory protected-surface comparisons are based on
  existence, mtime, and size rather than recursive directory content hashes
- safety boundary: no Keychain reset/allow action was clicked, no current
  `~/.codex/config.toml` repair was attempted, and no Phase 3 resume claim was
  made
- resume from here: CLOSED
