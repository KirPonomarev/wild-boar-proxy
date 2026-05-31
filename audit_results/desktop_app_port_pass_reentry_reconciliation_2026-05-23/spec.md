# Spec: DESKTOP_APP_PORT_PASS_REENTRY_RECONCILIATION

## Objective

Reconcile `MASTER_PLAN.md` slot 7 (`DESKTOP_APP_PORT_PASS`) against the current
desktop repo truth, determine whether the slot is already materially satisfied,
and record any closure drift or real desktop gap without reopening desktop
implementation by default.

## In Scope

- compare slot 7 requirements against the current Tk desktop shell
- compare slot 7 against existing desktop closeouts and evidence
- rerun focused desktop verification needed to support the verdict
- classify the outcome as satisfied, closure-pass-needed, or real gap
- record adjacency drift from slot 8 only when it affects honest slot 7
  classification

## Out of Scope

- new desktop feature buildout unless a real repo-owned gap is proven
- desktop UI redesign
- package/build-system rewrite
- new runtime semantics
- reopening already closed web contours

## Constraints

- current working Codex remains untouched
- desktop truth must stay packet-backed
- old closeout prose is not sufficient evidence by itself
- slot 8 may be inspected for adjacency only; it is not co-owned implementation
  scope by default

## Assumptions

- later repo truth is allowed to reconcile master-plan sequencing as long as it
  does not contradict canon
- the bundled-runtime Python remains the canonical interpreter for Tk tests
- existing desktop contours may be materially correct while still closure-stale

## Acceptance Criteria

- [x] slot 7 is classified as materially satisfied, closure-stale, or real gap
- [x] equivalence between slot 7 and current desktop repo truth is recorded with
  file-backed evidence
- [x] closure drift is named precisely instead of hidden behind a green verdict
- [x] focused desktop verification is rerun on the current branch
- [x] a fresh independent audit packet is produced before closeout

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli.CliTests.test_package_launchable_launcher_smoke_packaged_continuity_json_works -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/closeout.md audit_results/desktop_app_package_pass_2026-05-21/closeout.md`
- manual:
  - compare master-plan slot 7 wording against current `ui_shell.py` surfaces
  - compare existing closeouts against current branch/origin ancestry
- live evidence:
  - existing `desktop_continuity_smoke.json`
  - existing `desktop_packaged_continuity_smoke.json`

## Open Questions

- whether slot 8 should later receive its own reconciliation contour because its
  recorded git metadata no longer matches current branch truth
