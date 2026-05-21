# Spec: DESKTOP_APP_PACKAGE_PASS

## Objective

Determine whether the existing canonical desktop packaging path can satisfy the
master-plan requirement for a safe packaged desktop app that actually launches
and preserves the proven desktop continuity flow.

## In Scope

- localize the canonical packaging owner surface
- build one real package artifact through the canonical path
- verify package hygiene and archive boundaries
- determine whether the canonical artifact provides a packaged launch surface
- record evidence and stop honestly if the artifact contract is archive-only

## Out of Scope

- new packaging systems or alternate artifact kinds
- installer/notarization/distribution work
- desktop feature work or parity changes
- execution-core repair

## Constraints

- follow existing canonical packaging path only
- do not widen artifact semantics beyond what code/tests/docs already define
- do not infer packaged launch proof from local desktop continuity proof
- no private/runtime residue inside the artifact

## Assumptions

- the current canonical package path is the only acceptable baseline for this
  contour unless canon explicitly proves otherwise
- archive hygiene alone is insufficient to close the contour if packaged launch
  proof is absent

## Acceptance Criteria

- [x] canonical package build path localized
- [x] canonical package verify path localized
- [x] one real package artifact built and checksum/boundary-verified
- [x] artifact contents inspected for runtime/private residue
- [x] contour stopped honestly when packaged launch proof was found to be
  unsupported by the canonical path

## Verification

- tests:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_package_experimental_build_success_reports_changed_files tests.test_cli.CliTests.test_package_experimental_build_excludes_private_runtime_patterns_via_allowlist tests.test_cli.CliTests.test_package_experimental_verify_checksum_success tests.test_cli.CliTests.test_package_experimental_verify_rejects_checksum_mismatch tests.test_cli.CliTests.test_package_experimental_verify_rejects_boundary_violation tests.test_cli.CliTests.test_package_experimental_verify_rejects_symlink_boundary_bypass`
- commands:
  - `python3 -m wild_boar_proxy package experimental build --output-dir /private/tmp/wbp-package-proof --json`
  - `python3 -m wild_boar_proxy package experimental verify --manifest /private/tmp/wbp-package-proof/experimental-package.manifest.json --json`
  - `tar -tzf /private/tmp/wbp-package-proof/experimental-package.tar.gz`
- build:
  - `git diff --check`

## Open Questions

- which follow-up contour should introduce or admit a truly launchable packaged
  desktop artifact without violating the current canon boundary
