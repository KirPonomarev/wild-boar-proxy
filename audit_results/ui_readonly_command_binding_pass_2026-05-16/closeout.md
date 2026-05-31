<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_READONLY_COMMAND_BINDING_PASS Closeout

## Goal

Bind the existing basic UI to non-mutating read surfaces, committed packet
truth, and disabled live-action reasons, without executing runtime/auth/selector
mutations and without claiming execution-core repair closure or design-gate
readiness.

## Result

- status: `completed`
- final verdict: `GO_TO_UI_READONLY_BINDING_NEXT_SAFE_SLICE`
- next action: choose the next narrow product-safe UI binding slice, or stop
  product-safe UI work if it would require live mutation

## Contour Capsule

- goal: make live-readonly UI action metadata and dispatch truthfully represent
  parked runtime/live-action state
- branch: `codex/external-agent-lab-isolated`
- head: `ab270d0` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/contour.md`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_web_design_live_server`
  - `python3 -m unittest -q tests.test_web_design_ui.WebDesignUiTests.test_static_preview_applies_action_availability_from_metadata tests.test_web_design_ui.WebDesignUiTests.test_api_route_action_buttons_require_live_source_and_enabled_route`
  - `python3 -m unittest -q tests.test_web_design_command_adapter`
  - `python3 -m json.tool audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - runtime/live-action chain remains parked
  - UI still must not run live-mutating commands from live-readonly phase
  - this contour does not close execution-core repair and does not open the
    design gate
- next exact command:
  - `git status --short --untracked-files=no`

## Verification

- tests:
  - live-server action metadata and action endpoint tests passed
  - targeted frontend action-availability tests passed
- build:
  - `git diff --check`
  - decision packet JSON parse
- manual:
  - parked action set now includes `refresh_health_detail` and
    `stable_repair_plan`
  - metadata includes `availability_state`, `disabled_reason_code`, and
    `disabled_reasons`
  - client button datasets now preserve machine-readable source-gate,
    route-state, and deferred-route disabled reasons
  - `/api/action` blocks parked actions before command execution
  - no live runtime commands were run during this contour
- live verification:
  - not applicable; live commands were out of scope

## Artifacts

- spec:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
- report:
  - independent audit performed in-thread; two findings were corrected before
    staged verification

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: atomic contour commit is created by the closing orchestration after
  this staged file set passes verification; final hash is reported in the final
  orchestrator response because this file is part of that commit
- pushed: closing orchestration must push this branch before declaring the
  contour closed; final push evidence is reported in the final orchestrator
  response

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; no runtime/private data or raw command
  packets were committed`

## Notes

- blockers encountered:
  - independent audit found missing local disabled-reason binding for
    source/route gates; fixed before commit
  - independent audit found that git closeout evidence must not be claimed
    before commit/push; final evidence is reported after push
- follow-up contour:
  - `GO_TO_UI_READONLY_BINDING_NEXT_SAFE_SLICE`
- resume from here:
  `choose a narrow product-safe UI binding slice; do not run live-mutating commands; keep runtime/live-action repair parked`
