<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Desktop HTML Admission Closeout

## Contour

`UI_DESKTOP_HTML_RENDERER_ADMISSION_AND_PASSPORTS`

## Verdict

`DESKTOP_HTML_RENDERER_LANE_ADMITTED`

The provided render package is admitted as a visual baseline, not as runtime
canon. The next implementation target is `01_overview_dashboard` rendered from
fixtures in a local desktop HTML renderer.

## Renderer

`pywebview` is the first implementation-spike target.

The final packaging dependency is not locked in this contour because no desktop
HTML renderer dependency was installed here. The next contour must prove the
selected target with a local overview screen before command wiring.

## Scope Check

- Runtime behavior was not changed.
- CLI behavior was not changed.
- `ui_shell.py` was not changed.
- `web_ui.py` was not changed.
- No live command wiring was introduced.
- No dependency was installed.
- No state-file or log parsing was admitted as UI truth.

## Artifacts

- `audit_results/ui_desktop_html_renderer_decision.md`
- `audit_results/ui_desktop_html_admission_spec.md`
- `audit_results/ui_render_package_manifest.json`
- `audit_results/ui_render_surface_registry.json`
- `audit_results/ui_screen_passports.json`
- `audit_results/ui_desktop_html_admission_closeout.md`

## Screen Admission

- `00_brand_lockup`: reference only.
- `01_overview_dashboard`: first implementation target.
- `02_setup_client`: conditional setup candidate.
- `03_select_codex_client`: conditional settings/setup candidate.
- `04_accounts`: account pool target.
- `05_add_account_modal`: onboarding modal target.
- `06_diagnostics`: diagnostics target.
- `07_settings`: bounded settings display target.
- `08_import_existing`: deferred until command contract support exists.
- `09_confirm_action`: reusable confirmation modal target.

## Verification

Required verification for closeout:

- `python3 -m json.tool audit_results/ui_render_package_manifest.json`
- `python3 -m json.tool audit_results/ui_render_surface_registry.json`
- `python3 -m json.tool audit_results/ui_screen_passports.json`
- `git diff --check`

## Next Contour

`UI_DESKTOP_HTML_STATIC_OVERVIEW_WITH_FIXTURES`

The next contour should create the first static overview renderer surface from
fixtures only. It must not add live command wiring yet.
