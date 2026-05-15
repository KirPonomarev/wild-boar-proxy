<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_INSTALLER_DATA_LAYOUT_SETTINGS_SUBFLOW_PASS Closeout

## Goal

Implement a bounded Settings subflow for `Данные приложения / Installer Data Layout`: data directory display, package structure, permissions, snapshot/rollback, and dangerous operation states without making the web UI an installer, file picker, reset tool, config editor, or filesystem viewer.

## Result

- status: implemented and verified
- final verdict: PASS
- next action: owner review, then proceed to the next approved contour

## Contour Capsule

- goal: add `?screen=settings&section=data-layout` as a Settings-only subflow entered from `data-settings-section="data-installer"`, with disabled/deferred installer operations and no filesystem mutation.
- branch: `codex/external-agent-lab-isolated`
- head: pending final contour commit; implementation started after `8589ad9`.
- touched files: `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`; `git diff --check`; browser metric matrix captured at `1600x1000`.
- blocked risks: no command adapter action, no allowlist change, no live-server contract change, no desktop/native bridge, no real data directory access, no config/auth/log/registry reads.
- next exact command: run full unit suite, `git diff --check`, staged closeout resilience, commit, push.

## Verification

- structure inspection: Settings hub already had `data-settings-section="data-installer"`; this contour made it the entry to `section=data-layout` without adding a sidebar item or extending `SCREENS`.
- boundary inspection: data layout contains no editable path input, no file/directory picker, no browser-submitted path, no active destructive command, no `data-ui-action`, and no raw logs/config/auth/secrets.
- visual gate: all eight `1600x1000` captures pass `documentElement.scrollHeight <= 1000`, `main.scrollHeight <= main.clientHeight + 1`, `dataLayoutScreen.bottom <= 934`, no horizontal overflow, no clipped buttons/chips, `visibleSvgIcons === 0`, `visibleImgIcons > 0`, no input/select/textarea/canvas/pre, and no active forbidden action surface.
- route gate: `?screen=settings&section=data-layout` opens the subflow, `Назад к настройкам` returns to Settings hub, and sidebar remains on `Настройки`.
- unit suite: 93 tests passed across `tests.test_web_design_ui`, `tests.test_web_design_live_server`, and `tests.test_web_design_command_adapter`.

## Artifacts

- design source: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/screens/13_installer_data_layout.png`
- design tokens: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/specs/design_tokens.json`
- report: `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/closeout.md`
- screenshots:
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_initialized_healthy_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_permissions_warning_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_no_data_dir_known_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_snapshot_available_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_rollback_required_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_danger_operations_disabled_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_live_integration_failure_1600x1000.png`
  - `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/screenshots/data_layout_stale_1600x1000.png`
- metrics: `audit_results/ui_web_installer_data_layout_settings_subflow_pass_2026-05-15/metrics/*.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: final implementation commit recorded in git history and final operator note
- pushed: pending before final push

## Scope Check

- unrelated work mixed in: no; existing unrelated untracked `audit_results/external_lab_*` and `external_agent_lab/legacy/eval_results/` remain untouched.
- runtime touched: no.
- command adapter or allowlist touched: no.
- live server contract touched: no.
- desktop/native bridge touched: no.
- filesystem mutation/read touched: no.
- private-data risk reviewed: yes; the subflow uses inert safe display copy and fixture/preview state only.

## Notes

- The design reference contains active-looking installer buttons. This implementation intentionally renders those operations disabled/deferred because no admitted command surface exists in this contour.
- The subflow is a web UI preview/spec surface only. It must not be interpreted as installer readiness, writable proof, snapshot proof, or rollback proof.
- resume from here: CLOSED
