# Spec: Desktop Launchable Package Admission

## Objective

Add an admission-only owner path for a launchable desktop artifact so we can
prove a bounded packaged launch surface before returning to
`DESKTOP_APP_PACKAGE_PASS`.

## In Scope

- `package launchable build --output-dir <path> [--runtime-executable <path>] --json`
- `package launchable verify --manifest <path> --json`
- macOS `.app` bundle materialization for the admitted Tk shell baseline
- artifact hygiene enforcement against private/runtime residue
- one minimal packaged truth-backed lane (`installer init --json`)
- launchability proof for the packaged Tk shell

## Out of Scope

- full packaged Quick Start continuity proof
- installer UX, notarization, signing, or distribution rollout
- new product semantics beyond the proven desktop continuity flow
- execution-core repair unrelated to launchable package admission

## Constraints

- Canon order from `/Volumes/Work/wild-boar-proxy/AGENTS.md`
- no new truth source; packaged proof must stay packet + refresh backed
- no raw `token`, `secret`, `path`, `auth`, or `backend_id` inputs
- no private/runtime residue inside the artifact
- admission only; this contour does not close `DESKTOP_APP_PACKAGE_PASS`

## Assumptions

- admitted Tk shell remains the desktop baseline
- the bundled runtime at
  `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`
  is the canonical launchable runtime for this contour because host `python3`
  lacks `_tkinter`
- current full `tests.test_cli` contains pre-existing red unrelated to this
  contour, so contour regression proof must compare against `HEAD` evidence

## Acceptance Criteria

- [x] canonical `package launchable build/verify` owner surfaces exist
- [x] a launchable `.app` artifact is materialized and verified
- [x] artifact verification binds both bundle contents and companion metadata
- [x] artifact verification rejects symlink-based boundary bypasses
- [x] packaged shell launches and stays alive long enough to prove GUI startup
- [x] one minimal packaged truth-backed lane returns a machine packet
- [x] artifact hygiene excludes private/runtime residue

## Verification

- tests:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_package_launchable_build_requires_json_flag tests.test_cli.CliTests.test_package_launchable_verify_requires_json_flag tests.test_cli.CliTests.test_package_launchable_build_success_reports_changed_files tests.test_cli.CliTests.test_package_launchable_build_embeds_allowlisted_files_and_runtime_probe tests.test_cli.CliTests.test_package_launchable_verify_success tests.test_cli.CliTests.test_package_launchable_verify_rejects_boundary_violation tests.test_cli.CliTests.test_package_launchable_verify_rejects_symlink_boundary_bypass tests.test_cli.CliTests.test_package_launchable_verify_rejects_metadata_checksum_mismatch tests.test_cli.CliTests.test_package_launchable_launcher_smoke_installer_init_json_works`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_reports_unsupported_app_bundle_shape_in_owner_packet tests.test_cli.CliTests.test_launch_client_uses_absolute_system_open_under_hostile_path tests.test_cli.CliTests.test_installer_init_materializes_repo_owned_owner_helper_chain`
  - bundled runtime non-CLI suite:
    `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
- build:
  - `python3 -m wild_boar_proxy package launchable build --output-dir <temp> --runtime-executable <bundled-python> --json`
  - `python3 -m wild_boar_proxy package launchable verify --manifest <temp>/launchable-package.manifest.json --json`
- manual:
  - packaged launcher `--smoke-installer-init-json`
  - packaged launcher UI liveness after `1.5s`
- live evidence:
  - `audit_results/desktop_launchable_package_admission_pass_2026-05-21/evidence/desktop_launchable_smoke.json`
  - `audit_results/desktop_launchable_package_admission_pass_2026-05-21/evidence/head_comparison_regressions.json`

## Open Questions

- whether the next `DESKTOP_APP_PACKAGE_PASS` should keep the bundled runtime
  requirement or add a stricter runtime-selection contract
