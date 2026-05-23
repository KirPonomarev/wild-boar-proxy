# Spec: DESKTOP_APP_PACKAGE_PASS_REENTRY_RECONCILIATION

## Objective

Reconcile `MASTER_PLAN.md` slot 8 (`DESKTOP_APP_PACKAGE_PASS`) against current
repo truth, determine whether the package slot is already materially satisfied,
and record any closure drift or real packaging gap without reopening package
implementation by default.

## In Scope

- compare slot 8 requirements against the current package contour and evidence
- compare slot 8 against current branch/origin git truth
- rerun focused package verification needed to support the verdict
- classify the outcome as satisfied, closure-pass-needed, or real package gap
- keep slot 7 reopened only if slot 8 proof directly contradicts it

## Out of Scope

- new package/build implementation unless a real repo-owned gap is proven
- desktop UI redesign
- runtime repair unrelated to package proof
- installer, notarization, signing, or distribution expansion

## Constraints

- current working Codex remains untouched
- package truth must stay packet-backed
- old closeout prose is not sufficient evidence by itself
- slot 7 remains settled unless slot 8 evidence directly breaks it

## Assumptions

- later repo truth is allowed to reconcile master-plan sequencing as long as it
  does not contradict canon
- the bundled-runtime Python remains the canonical interpreter for Tk tests
- existing package contour may be materially correct while still closure-stale

## Acceptance Criteria

- [x] slot 8 is classified as materially satisfied, closure-stale, or real gap
- [x] equivalence between slot 8 and current package repo truth is recorded with
  file-backed evidence
- [x] closure drift is named precisely instead of hidden behind a green verdict
- [x] focused package verification is rerun on the current branch
- [x] a fresh independent audit packet is produced before closeout

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli.CliTests.test_package_launchable_launcher_smoke_packaged_continuity_json_works -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/desktop_app_package_pass_2026-05-21/closeout.md audit_results/desktop_app_port_pass_reentry_reconciliation_2026-05-23/closeout.md`
- manual:
  - compare master-plan slot 8 wording against current package evidence and
    branch/origin ancestry
- live evidence:
  - existing `desktop_packaged_continuity_smoke.json`
  - existing `package_contents_scan.json`

## Open Questions

- whether slot 8 should later get a fresh implementation contour only if the
  package artifact path or boundary proof regresses on a future branch
