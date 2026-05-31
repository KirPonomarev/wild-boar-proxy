# UI Web Visual Rebase To Original Closeout

Contour: `UI_WEB_VISUAL_REBASE_TO_ORIGINAL_RENDER`

Date: 2026-05-13

Status: passed, ready for commit.

## Scope

This contour is a visual correction pass. It returns the web design UI closer to
the source render package and the owner correction spec without changing command
meaning, runtime truth, action availability, or desktop scope.

Changed files:

- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `tests/test_web_design_ui.py`
- `audit_results/ui_web_visual_rebase_to_original_matrix_2026-05-13.json`
- `audit_results/ui_web_visual_rebase_to_original_browser_smoke_2026-05-13.json`
- `audit_results/ui_web_visual_rebase_to_original_independent_audit_2026-05-13.json`
- `audit_results/ui_web_visual_rebase_to_original_closeout_2026-05-13.md`

## Visual Corrections

- Restored mono-first UI typography with `SF Mono` as the visual baseline.
- Fixed sidebar logo width to the source-render 112 px brand mark.
- Restored header rhythm closer to the render package with 24 px header gap and
  margin.
- Restored 40 px control height for buttons, inputs, search, and filter
  segments.
- Restored overview grid, action tile, KPI card, and log spacing closer to the
  source render package.
- Reduced heavy heading/numeric weights toward a semibold hierarchy instead of
  broad boldness.
- Kept useful previous stabilization: responsive containment, table overflow
  guard, readable account action groups, error/stale clarity, and bounded modal
  overflow.

## Private Reference Lane

A generic private reference lookup was attempted outside repo evidence, but it
timed out and contributed no adopted implementation decision.

No private reference-service names, URLs, screenshots, tokens, install notes, or
research notes are recorded in this repo.

## Browser Smoke

Smoke target: `http://127.0.0.1:8788`

Runner: local fake `MappingRunner(live_payloads())`

Observed:

- Overview loaded in live mode with `Обзор` and live-readonly footer.
- Accounts loaded with `Аккаунты`.
- `validate_account` for `acct-active` was confirmed once.
- Action ledger showed `status=ok`, `refresh=live refresh ok`, and retained the
  canonical refreshed JSON truth note.
- Diagnostics loaded as support-artifact view.
- Settings loaded as command-packet bounded view.
- Setup/select/import loaded with inert deferred copy.

A long multi-screen browser script timed out in the browser tool; the smoke was
split into shorter checks and completed successfully.

## Verification

```text
node --check wild_boar_proxy/web_design_ui/scripts/overview.js
OK
```

```text
python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q
Ran 70 tests in 2.045s
OK
```

```text
python3 -m unittest discover -s tests -q
Ran 564 tests in 228.157s
OK
```

## Boundary

- `runtime.py` was not touched.
- Desktop files were not touched.
- Server allowlist was not changed.
- Command adapter argv templates were not changed.
- No new `ui_action` was added.
- No real runtime command was executed.
- Dirty external-agent tail was not staged or edited.

## Independent Audit

Independent audit result: `PASS`

Auditor confirmed:

- Diff is limited to visual CSS and static test coverage.
- No runtime, server, adapter, or desktop files appear in the contour diff.
- The visual changes are plausibly closer to the source render package and owner
  correction spec.
- Contour artifacts are internally consistent.
- No private reference-service identifiers, URLs, tokens, install prompts,
  downloaded screenshots, or private notes were found by inspection.

Residual risk: pixel-level closeness to the source render package remains a
manual visual-review concern for the pre-desktop freeze.

## Result

The UI has been visually rebased closer to the original warm technical editorial
direction while preserving the already-proven operator flow. The contour is ready
for final leak scan, commit, and push.
