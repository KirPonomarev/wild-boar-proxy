<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_SETTINGS_CLIENT_LAUNCH_SUBFLOW_PASS Closeout

## Goal

Implement a bounded Settings subflow for `Client / Launch`: selected Codex client status, launch readiness, bounded launch dispatch, candidate-selection boundary, compact last command state, and deferred native actions without making the web UI a file picker, path editor, config writer, or runtime truth source.

## Result

- status: implemented and verified
- final verdict: PASS
- next action: owner review, then proceed to the next approved contour

## Contour Capsule

- goal: add `?screen=settings&section=client` as a Settings-only subflow entered from the existing `Client / Launch` hub card, with packet/fixture-owned client status, admitted launch actions only, and no browser path/file/native mutation surface.
- branch: `codex/external-agent-lab-isolated`
- head: pending final contour commit; implementation started after `e8bb4ba`.
- touched files: `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`; `git diff --check`; browser metric matrix captured at `1600x1000`.
- blocked risks: no command adapter change, no allowlist change, no live-server contract change, no desktop/native bridge, no config/state/log reads, no editable path input, no file picker, no launch success claim without packet proof.
- next exact command: stage the declared scope, run staged closeout resilience, commit, push.

## Verification

- preflight: `git status --short --untracked-files=no` was clean for tracked files; `git log --oneline -n 6` showed previous closed contour commit `e8bb4ba`.
- structure inspection: Settings now supports sections `hub`, `runtime`, `client`, and `data-layout`; `client` is not a sidebar screen and is not added to `SCREENS`.
- route gate: `?screen=settings&section=client` opens the Client / Launch subflow; `Назад к настройкам` returns to the Settings hub.
- boundary inspection: the subflow exposes exactly these UI actions: `launch_client_dispatch` and `launch_smoke`.
- forbidden surface check: no file input, no editable path input, no browser-submitted client path, no working directory payload, no raw command payload, no argv/shell fields, no direct config writes, no filesystem client discovery, no false `client running` or `Клиент запущен` copy.
- visual gate: all eight `1600x1000` captures pass `documentElement.scrollHeight <= 1000`, `main.scrollHeight <= main.clientHeight + 1`, `clientLaunchPanel.bottom <= 934`, no horizontal overflow, no clipped buttons/chips/content/path, `visibleSvgIcons === 0`, `visibleImgIcons > 0`, and no input/select/textarea/canvas.
- unit suite: 95 tests passed across `tests.test_web_design_ui`, `tests.test_web_design_live_server`, and `tests.test_web_design_command_adapter`.

## Artifacts

- design source: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/screens/16_settings_client_launch.png`
- design tokens: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/specs/design_tokens.json`
- report: `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/closeout.md`
- screenshots:
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_available_ready_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_unavailable_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_candidate_deferred_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_dispatch_available_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_dispatch_disabled_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_dispatch_ok_refresh_pending_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_runtime_down_1600x1000.png`
  - `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/screenshots/client_launch_live_integration_failure_1600x1000.png`
- metrics: `audit_results/ui_web_settings_client_launch_subflow_pass_2026-05-15/metrics/*.json`

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
- private-data risk reviewed: yes; paths are inert fixture/packet display only, no secrets are rendered, and no browser payload includes path, argv, shell, token, or config data.

## Notes

- The design reference includes a launch-oriented control surface. This implementation scopes launch copy to `dispatch requested`, not app/session/runtime truth.
- Manual client selection remains linked to the existing Select Client screen and is described as desktop/native-only for file picking.
- Human-open/Finder-style actions remain disabled/deferred in this Settings subflow.
- resume from here: CLOSED
