# DESKTOP_APP_PACKAGE_PASS Closeout

## Goal

Determine whether the existing canonical packaging path can close the desktop
package contour with real packaged-launch proof, safe artifact hygiene, and the
baseline packaged continuity path required by the master plan.

## Result

- status: `STOP_AND_DIAGNOSE`
- final verdict:
  `CANONICAL_DESKTOP_PACKAGE_PATH_IS_ARCHIVE_ONLY_AND_CANNOT_PROVE_PACKAGED_LAUNCH`
- next action:
  open a narrow launchable-artifact admission contour before retrying
  `DESKTOP_APP_PACKAGE_PASS`

## Contour Capsule

- goal:
  verify whether the repo's canonical desktop packaging path yields a safe,
  launchable desktop artifact or only an allowlisted archive
- branch: `codex/external-agent-lab-isolated`
- head: `1929c56aa2729e2457e1165898f0bcb30cdc097c`
- touched files:
  - `audit_results/desktop_app_package_pass_2026-05-21/spec.md`
  - `audit_results/desktop_app_package_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/closeout.md`
  - `audit_results/desktop_app_package_pass_2026-05-21/independent_audit.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_build_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_verify_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_archive_summary.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_contract_scan.json`
- tests run:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_package_experimental_build_success_reports_changed_files tests.test_cli.CliTests.test_package_experimental_build_excludes_private_runtime_patterns_via_allowlist tests.test_cli.CliTests.test_package_experimental_verify_checksum_success tests.test_cli.CliTests.test_package_experimental_verify_rejects_checksum_mismatch tests.test_cli.CliTests.test_package_experimental_verify_rejects_boundary_violation tests.test_cli.CliTests.test_package_experimental_verify_rejects_symlink_boundary_bypass`
  - `python3 -m wild_boar_proxy package experimental build --output-dir /private/tmp/wbp-package-proof --json`
  - `python3 -m wild_boar_proxy package experimental verify --manifest /private/tmp/wbp-package-proof/experimental-package.manifest.json --json`
  - `tar -tzf /private/tmp/wbp-package-proof/experimental-package.tar.gz`
  - `git diff --check`
- blocked risks:
  - the current canonical packaging path proves archive hygiene only and does
    not expose a launchable packaged desktop application
  - closing this contour as success would infer packaged-launch truth from a
    non-launchable artifact and violate canon
- next exact command:
  - `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - targeted packaging CLI tests prove build success, checksum verification, and
    boundary rejection behavior for the canonical package path
- build:
  - real package build produced `experimental-package.tar.gz`,
    `experimental-package.manifest.json`, and
    `experimental-package.metadata.json`
  - real verify passed checksum and archive boundary validation
- manual:
  - archive content inspection showed repo docs/source only
  - no `.app`, `.pkg`, or root executable entry was present inside the
    canonical artifact
- live verification:
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_build_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_verify_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_archive_summary.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_contract_scan.json`

## Artifacts

- spec:
  - `audit_results/desktop_app_package_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_build_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_verify_result.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_archive_summary.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/package_contract_scan.json`
- report:
  - `audit_results/desktop_app_package_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit:
  `closeout drafted before the stop-and-diagnose commit; final stop commit is recorded in git history after resilience passes`
- pushed:
  `closeout drafted before the stop-and-diagnose push; final push is recorded in git history after the closing commit`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; the built archive passed boundary checks and the recorded evidence contains only command packets, file names, and line references`

## Notes

- blockers encountered:
  - the canonical packaging contract is explicitly archive-oriented
  - no packaged launch command or packaged-launch verifier exists on the owner
    surface
  - the built artifact is a tarball of allowlisted repo files rather than a
    launchable desktop app bundle
- follow-up contour:
  - `DESKTOP_LAUNCHABLE_PACKAGE_ADMISSION_PASS`
- resume from here:
  `CLOSED / open DESKTOP_LAUNCHABLE_PACKAGE_ADMISSION_PASS before retrying DESKTOP_APP_PACKAGE_PASS`
