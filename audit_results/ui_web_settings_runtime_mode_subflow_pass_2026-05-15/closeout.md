<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_SETTINGS_RUNTIME_MODE_SUBFLOW_PASS Closeout

## Goal

Implement a bounded Settings subflow for `Runtime / Mode`: desired/effective mode, source of truth, safe mode actions, verification actions, compact last command state, and deferred recovery apply controls without making Settings a repair center, rollout panel, or config editor.

## Result

- status: implemented and verified
- final verdict: PASS
- next action: owner review, then proceed to the next approved contour

## Contour Capsule

- goal: add `?screen=settings&section=runtime` as a Settings-only subflow entered from the existing `Runtime / Mode` hub card, with packet-owned mode truth, admitted action buttons only, and no direct config/state/log access.
- branch: `codex/external-agent-lab-isolated`
- head: pending final contour commit; implementation started after `6da13a3`.
- touched files: `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`; `git diff --check`; browser metric matrix captured at `1600x1000`.
- blocked risks: no command adapter change, no allowlist change, no live-server contract change, no desktop/native bridge, no config/state/log file reads, no active `stable_repair_apply`, no rollout or policy controls.
- next exact command: run staged closeout resilience, commit, push.

## Verification

- preflight: `git status --short --untracked-files=no` was clean for tracked files; `git log --oneline -n 5` showed previous closed contour commit `6da13a3`.
- structure inspection: Settings now supports sections `hub`, `runtime`, and `data-layout`; `runtime` is not a sidebar screen and is not added to `SCREENS`.
- route gate: `?screen=settings&section=runtime` opens the Runtime / Mode subflow; `Назад к настройкам` returns to the Settings hub.
- boundary inspection: runtime subflow exposes exactly these UI actions: `set_mode_managed`, `set_mode_stable`, `sync_runtime`, `launch_smoke`, `refresh_health_detail`, and `stable_repair_plan`.
- forbidden actions check: no `stable_repair_apply`, no config/path/raw command payload, no rollout/policy active controls, no form save, no editable inputs, and no direct runtime file read.
- visual gate: all nine `1600x1000` captures pass `documentElement.scrollHeight <= 1000`, `main.scrollHeight <= main.clientHeight + 1`, `runtimeModePanel.bottom <= 934`, no horizontal overflow, no clipped buttons/chips, `visibleSvgIcons === 0`, `visibleImgIcons > 0`, no input/select/textarea/canvas, and no Source of truth card overflow.
- unit suite: 94 tests passed across `tests.test_web_design_ui`, `tests.test_web_design_live_server`, and `tests.test_web_design_command_adapter`.

## Artifacts

- design source: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/screens/15_settings_runtime_mode.png`
- design tokens: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/specs/design_tokens.json`
- report: `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/closeout.md`
- screenshots:
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_managed_healthy_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_stable_healthy_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_desired_effective_mismatch_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_stale_data_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_runtime_down_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_command_ok_refresh_pending_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_refresh_failed_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_repair_plan_apply_deferred_1600x1000.png`
  - `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/screenshots/runtime_mode_live_integration_failure_1600x1000.png`
- metrics: `audit_results/ui_web_settings_runtime_mode_subflow_pass_2026-05-15/metrics/*.json`

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
- config/state/log files touched: no.
- private-data risk reviewed: yes; the subflow uses packet/fixture labels and does not expose raw paths, argv, logs, policy stages, or config writes.

## Notes

- The design reference includes active-looking mode controls. This implementation treats mode switch requests as admitted UI actions that require confirmation and refresh proof before success copy.
- Recovery apply remains disabled/deferred in this Settings subflow. Planning is allowed through the already admitted `stable_repair_plan`; apply is intentionally out of scope.
- resume from here: CLOSED
