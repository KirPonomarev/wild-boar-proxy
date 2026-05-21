# Spec: DESKTOP_APP_PACKAGE_PASS

## Objective

Prove that the admitted launchable desktop package path can carry the already
proven Quick Start continuity flow without widening semantics, leaking
private/runtime residue, or inventing a new truth source.

## In Scope

- build the canonical launchable package artifact through `package launchable build`
- verify manifest, checksum, boundary, and runtime baseline through
  `package launchable verify`
- launch the packaged Tk shell with the bundled runtime baseline
- prove baseline packaged continuity:
  Quick Start opens, account truth loads, API truth loads, `Check All` reaches
  `ready`, and the ledger records `quick_start_check_all`
- capture machine evidence for hygiene, launch, continuity, and the residual
  full-CLI red tail

## Out of Scope

- installer, notarization, signing, auto-update, or distribution work
- from-empty rebuild or repeated live onboarding
- redesign or desktop polish
- execution-core repair unrelated to packaged continuity

## Constraints

- use the canonical launchable artifact path already admitted by
  `DESKTOP_LAUNCHABLE_PACKAGE_ADMISSION_PASS`
- use the bundled runtime when host `python3` does not provide `_tkinter`
- do not infer packaged continuity from local desktop continuity
- do not allow packaged smoke to mutate route-truth during proof
- do not close on partial or degraded bundle states

## Assumptions

- a preflight `external-models check --route ... --json` in the harness is an
  allowed setup mutation because the contour baseline is continuity, not
  from-empty rebuild
- the six failing tests in the full `tests.test_cli` suite are pre-existing
  unless evidence proves otherwise

## Acceptance Criteria

- [x] canonical launchable artifact builds through `package launchable build`
- [x] package verification passes through `package launchable verify`
- [x] package contents scan shows no forbidden private/runtime residue
- [x] packaged launcher starts the admitted Tk shell
- [x] packaged Quick Start continuity reaches `source=live_sandbox`,
      `account_status=ok`, `api_status=enabled`, `bundle_verdict=ready`
- [x] packaged ledger records `quick_start_check_all`
- [x] packaged run does not add a second `/v1/chat/completions` request during
      the packaged smoke itself
- [x] independent re-audit finds no medium+ issues after the packaged-smoke fix
- [x] full `tests.test_cli` red tail is preserved as residual risk only, with
      same six failures reproduced on clean `f11bcd1`

## Verification

- tests:
  - `python3 -m unittest tests.test_cli.CliTests.test_package_launchable_launcher_smoke_packaged_continuity_json_works -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `python3 -m unittest -q tests.test_cli` (fails with six pre-existing failures)
- build:
  - `python3 -m wild_boar_proxy package launchable build --output-dir audit_results/desktop_app_package_pass_2026-05-21/evidence/package-output --runtime-executable /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 --json`
  - `python3 -m wild_boar_proxy package launchable verify --manifest audit_results/desktop_app_package_pass_2026-05-21/evidence/package-output/launchable-package.manifest.json --json`
- manual:
  - packaged launcher `WildBoarProxy.app/Contents/MacOS/WildBoarProxy --smoke-packaged-continuity-json`
- live evidence:
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/desktop_packaged_continuity_smoke.json`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/full_test_cli_current.txt`
  - `audit_results/desktop_app_package_pass_2026-05-21/evidence/head_comparison_regressions.json`

## Open Questions

- whether the six pre-existing `tests.test_cli` failures should be isolated into
  a dedicated repair contour after this package pass is merged
