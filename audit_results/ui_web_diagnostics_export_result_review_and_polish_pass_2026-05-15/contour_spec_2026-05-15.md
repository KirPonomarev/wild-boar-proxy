<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: UI Web Diagnostics Export Result Review And Polish Pass

## Objective

Polish the existing `diagnostics export --json` result surface so it is rendered
only as a support artifact result, not as runtime health truth or diagnostics
history truth.

This contour keeps the existing command surface and action allowlist unchanged.
It does not read diagnostics bundle contents, logs, runtime state files, or raw
command output.

## In Scope

- Normalize diagnostics export redaction metadata into `enabled`, `unreported`,
  or `failed`.
- Keep `bundle_path` as basename/reference only.
- Keep `changed_files` as marker/count only.
- Render export result states as support artifact states:
  - `created`
  - `redaction_unreported`
  - `redaction_failed`
  - `artifact_unavailable`
  - `invalid_json`
  - `timeout`
  - `command_error`
  - `integration_failure`
- Ensure missing redaction proof is not shown as enabled.
- Ensure redaction failure is red.
- Ensure successful support artifact rendering is blue/neutral, not runtime
  health green.
- Add tests for redaction status normalization and UI rendering.

## Out of Scope

- Runtime changes.
- Command adapter changes.
- Allowlist expansion.
- Diagnostics history packet implementation.
- Diagnostics bundle parsing.
- Raw log viewing.
- Desktop/native changes.

## Constraints

- `export_diagnostics` remains `support_artifact`.
- `diagnostics export --json` is not a runtime healthcheck.
- Browser payload for export must remain `ui_action=export_diagnostics` only.
- UI must not invent redaction proof.
- UI must not show absolute paths or raw changed-file paths.

## Acceptance Criteria

- [x] `bundle_path` is rendered as basename/reference only.
- [x] `changed_files` is rendered as count/marker only.
- [x] `redaction_status` is normalized to `enabled`, `unreported`, or `failed`.
- [x] `redaction_unreported` renders amber, not blue/green.
- [x] `redaction_failed` renders red.
- [x] Export success does not claim runtime health.
- [x] Export result remains support artifact only.
- [x] No runtime, command adapter, allowlist, diagnostics history, or desktop
  implementation changes are included.

## Verification

- tests: `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `python3 -m py_compile wild_boar_proxy/web_design_live_server.py`
- manual: `rg` scans for export copy, raw path/log/argv/JSON terms, redaction states, and forbidden external reference traces.
- live evidence: not applicable; no live runtime mutation or new command surface.

## Open Questions

- Desktop shell parity for diagnostics export path display remains a later
  desktop/native contour, not part of this web/live-server contour.
