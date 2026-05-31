# DESKTOP_LAUNCHABLE_PACKAGE_ADMISSION_PASS Closeout

## Goal

Admit a canonical launchable desktop package owner path without falsely closing
the broader packaged-product contour.

## Result

- status: completed
- final verdict: `closed_success`
- next action: return to `DESKTOP_APP_PACKAGE_PASS`

## Contour Capsule

- goal: Add and prove a bounded `package launchable build/verify` owner surface for a launchable `.app` artifact with one minimal truth-backed packaged lane.
- branch: codex/external-agent-lab-isolated
- head: 8fbb16553ec53206fe96f5f759450149b8184636
- touched files: COMMAND_API.md; wild_boar_proxy/cli.py; wild_boar_proxy/runtime.py; tests/test_cli.py; audit_results/desktop_launchable_package_admission_pass_2026-05-21/*
- tests run: targeted launchable CLI suite (9 tests, pass); related existing CLI suite (3 tests, pass); bundled non-CLI suite (248 tests, pass); bundled ui_shell suite (113 tests, pass); `node --check` pass; full `tests.test_cli` re-run shows 6 known red failures that reproduce independently from this contour family.
- blocked risks: host `python3` lacks `_tkinter` and `PIL`, so canonical UI/package proof uses the bundled runtime; full `tests.test_cli` still contains 6 known red failures outside this contour; full packaged continuity remains intentionally out of scope.
- next exact command: python3 -m wild_boar_proxy package launchable build --output-dir /tmp/wbp-package-proof --runtime-executable /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 --json

## Verification

- tests:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_package_launchable_build_requires_json_flag tests.test_cli.CliTests.test_package_launchable_verify_requires_json_flag tests.test_cli.CliTests.test_package_launchable_build_success_reports_changed_files tests.test_cli.CliTests.test_package_launchable_build_embeds_allowlisted_files_and_runtime_probe tests.test_cli.CliTests.test_package_launchable_verify_success tests.test_cli.CliTests.test_package_launchable_verify_rejects_boundary_violation tests.test_cli.CliTests.test_package_launchable_verify_rejects_symlink_boundary_bypass tests.test_cli.CliTests.test_package_launchable_verify_rejects_metadata_checksum_mismatch tests.test_cli.CliTests.test_package_launchable_launcher_smoke_installer_init_json_works`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_reports_unsupported_app_bundle_shape_in_owner_packet tests.test_cli.CliTests.test_launch_client_uses_absolute_system_open_under_hostile_path tests.test_cli.CliTests.test_installer_init_materializes_repo_owned_owner_helper_chain`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `python3 -m unittest -q tests.test_cli` (known red baseline persisted at 6 failures; see evidence)
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `python3 -m wild_boar_proxy package launchable build --output-dir <temp> --runtime-executable <bundled-python> --json`
  - `python3 -m wild_boar_proxy package launchable verify --manifest <temp>/launchable-package.manifest.json --json`
- manual:
  - packaged launcher `--smoke-installer-init-json`
  - packaged launcher UI liveness after `1.5s`
- live verification:
  - `audit_results/desktop_launchable_package_admission_pass_2026-05-21/evidence/desktop_launchable_smoke.json`
  - `audit_results/desktop_launchable_package_admission_pass_2026-05-21/evidence/head_comparison_regressions.json`

## Artifacts

- spec: `audit_results/desktop_launchable_package_admission_pass_2026-05-21/spec.md`
- packet: `audit_results/desktop_launchable_package_admission_pass_2026-05-21/evidence/desktop_launchable_smoke.json`
- report: `audit_results/desktop_launchable_package_admission_pass_2026-05-21/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered: two medium audit findings in launchable verify (symlink bypass and metadata integrity) plus one medium source-side symlink ingress issue; all three were fixed before closeout.
- follow-up contour: DESKTOP_APP_PACKAGE_PASS
- resume from here: DESKTOP_APP_PACKAGE_PASS
