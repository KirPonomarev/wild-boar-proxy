<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_READONLY_COMMAND_BINDING_PASS Contour

CONTOUR:
UI_READONLY_COMMAND_BINDING_PASS

Goal:
Bind the existing basic UI to non-mutating read surfaces, committed packet
truth, and disabled live-action reasons, without executing runtime/auth/selector
mutations and without claiming execution-core repair closure or design-gate
readiness.

Size:
M

Risk level:
medium

Decision owner:
Maintainer for UI/control-layer implementation. Canon owns disputed runtime
truth interpretation. Operator owns live mutation, which is out of scope.

Mode:
implementation, product-safe / no-live-mutation

In scope:
- Inventory existing UI screens, panels, buttons, action metadata, and live
  server command dispatch.
- Bind UI action metadata to disabled live-action reasons for the parked
  runtime/live-action chain.
- Ensure live-readonly `/api/action` does not dispatch parked live actions.
- Persist disabled-action reason fields to client button metadata.
- Add targeted tests for server metadata, action endpoint blocking, and client
  action availability mapping.
- Add contour packet and closeout under
  `audit_results/ui_readonly_command_binding_pass_2026-05-16/`.

Out of scope:
- No direct live runtime CLI execution.
- No `sync --json`.
- No `launch smoke --json`.
- No `stable repair --apply --json`.
- No onboarding.
- No auth materialization.
- No selector retry.
- No route mutation.
- No stage/pilot proof.
- No rich UI expansion.
- No design polish.
- No new flows beyond truth/action binding.
- No claim of `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.

Assumptions:
- `MASTER_PLAN.md` allows a product-safe UI lane limited to read-only truth and
  disabled live-action reasons.
- Unknown command/action surfaces must default disabled.
- Live-readonly action dispatch remains narrower than full action mode.
- Existing tests use fake command runners and are not live runtime commands.

Inputs:
- docs:
  - `MASTER_PLAN.md`
  - `CANON.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
- code:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
- runtime evidence:
  - no fresh live runtime packets; existing committed planning truth only

Commands / files:
- Read:
  - UI live server, command adapter, frontend action mapping, UI tests
- Write:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/contour.md`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`

Acceptance criteria:
- Live-readonly metadata marks parked runtime/auth/selector/support actions as
  unavailable with machine-readable disabled reasons.
- Live-readonly `/api/action` blocks parked actions before command dispatch.
- Unknown metadata defaults to disabled on the client.
- Client buttons preserve machine-readable availability state and disabled
  reason fields.
- No runtime/private files are committed.
- No live-mutating command is run as part of this contour.
- `UI_READONLY_COMMAND_BINDING_PASS` remains a contour label, not a canon truth
  token.

Verification:
- tests:
  - targeted `tests.test_web_design_live_server`
  - targeted `tests.test_web_design_ui`
- build:
  - `git diff --check`
- manual:
  - inspect changed action metadata and parked action set
  - verify no live runtime command invocation was used
- live packet:
  - none; live commands are out of scope

Artifacts:
- spec:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if UI binding requires running a live-mutating command.
- `STOP_AND_DIAGNOSE` if a supposedly read-only path writes runtime state or
  lock files.
- `STOP_AND_DIAGNOSE` if any runtime/auth/selector action appears enabled
  without canon-backed admission.
- `STOP_AND_DIAGNOSE` if the work drifts into design polish, rich UI expansion,
  or new product flows.

Closeout:
- verification complete:
  - targeted UI/live-server tests
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- commit:
  - required after staged verification
- push:
  - required by `DELIVERY_RULES.md`
- next contour:
  - `GO_TO_UI_READONLY_BINDING_NEXT_SAFE_SLICE`
