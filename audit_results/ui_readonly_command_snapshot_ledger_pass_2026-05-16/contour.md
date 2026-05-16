<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_READONLY_COMMAND_SNAPSHOT_LEDGER_PASS Contour

CONTOUR:
UI_READONLY_COMMAND_SNAPSHOT_LEDGER_PASS

Goal:
Bind existing read-only snapshot command summaries into the UI as bounded
evidence of the last loaded truth surface, without adding new command execution,
persistence, runtime repair, live mutation, or design polish.

Size:
M

Risk level:
medium

Decision owner:
Maintainer for UI/control-layer implementation. Canon owns disputed runtime
truth interpretation. Operator owns live mutation, which is out of scope.

Mode:
implementation, product-safe / read-only UI binding

In scope:
- Inventory current read-only snapshot command summaries returned by
  `/api/live-readonly`, `/api/accounts-readonly`, and
  `/api/api-connections-readonly`.
- Render a separate read-only snapshot command ledger/summary in the UI.
- Keep this ledger distinct from the existing session action ledger.
- Show only bounded public command fields:
  - `command_id`
  - `role`
  - `status`
  - `ui_state`
  - `machine_error_code`
  - `exit_code`
  - `next_action`
- Preserve current disabled live-action reasons from the previous contour.
- Show command outcomes as packet evidence only, not runtime-health proof.
- Add tests that verify bounded rendering and no leakage of raw/private data.
- Add contour packet and closeout under
  `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/`.

Out of scope:
- No new command execution surface.
- No direct live runtime CLI execution.
- No polling/autorefresh of new runtime commands.
- No persisted command history.
- No import of old packet archives.
- No raw packet body display.
- No argv display.
- No filesystem path display.
- No secrets/private runtime data display.
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
- No claim of `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.

Assumptions:
- `MASTER_PLAN.md` allows product-safe UI work limited to read-only truth
  display, command ledger/history display, and disabled live-action reasons.
- The previous `UI_READONLY_COMMAND_BINDING_PASS` closed disabled live-action
  reason binding.
- Existing read-only snapshot payloads already expose bounded public command
  summaries through `commands`.
- Unknown or absent command summary data must render as missing/unknown, not as
  success.
- `command status ok` means command packet outcome only; it does not prove
  runtime health, repair closure, selector progress, auth readiness, onboarding
  readiness, or pilot readiness.

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
  - `WORKFLOW_OS_V1_2.md`
- code:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
- prior contour evidence:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/closeout.md`
- runtime evidence:
  - no fresh live runtime packets required
  - no live mutation authorized or needed

Commands / files:
- Read:
  - `MASTER_PLAN.md`
  - `CANON.md`
  - read-only live server snapshot builders
  - frontend overview rendering
  - existing action ledger tests
- Write:
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_ui.py`
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/contour.md`
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/closeout.md`

Acceptance criteria:
- UI renders a read-only snapshot command ledger/summary for the last loaded
  snapshot truth surface.
- The read-only snapshot command ledger is visually and logically distinct from
  the existing session action ledger.
- The ledger uses only existing snapshot `commands` data; it does not trigger
  new commands.
- Rendered command fields are bounded to the public command summary fields.
- Missing command data renders as unknown/missing, not green/success.
- `command status ok` is labelled as command packet outcome only.
- Snapshot warnings or integration failure prevent false-green presentation.
- No raw packet body is rendered.
- No argv is rendered.
- No filesystem paths are rendered.
- No secrets/private runtime data are rendered.
- No persisted history is created.
- No runtime/private files are committed.
- Live-mutating actions remain disabled under parked runtime/live-action truth.
- The contour does not claim execution-core repair, selector refresh success,
  exact auth-source readiness, onboarding readiness, stage proof, or pilot
  readiness.

Verification:
- tests:
  - `python3 -m unittest -q tests.test_web_design_ui`
  - `python3 -m unittest -q tests.test_web_design_live_server`
- build:
  - `python3 -m json.tool audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
- manual:
  - inspect changed UI rendering paths
  - inspect that session action ledger and snapshot command ledger are separate
  - inspect no new command execution path was added
  - inspect no raw packet/path/argv/private data can render
- live packet:
  - none; live commands are out of scope

Artifacts:
- spec:
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if implementation requires adding or running a live
  command.
- `STOP_AND_DIAGNOSE` if command ledger display requires raw packet bodies.
- `STOP_AND_DIAGNOSE` if command status ok would be presented as runtime
  healthy.
- `STOP_AND_DIAGNOSE` if UI binding touches selector/auth/onboarding/stage/pilot
  behavior.
- `STOP_AND_DIAGNOSE` if runtime/private data, local paths, argv, or secrets can
  appear in UI or committed artifacts.
- `STOP_AND_DIAGNOSE` if the work drifts into rich UI expansion or design
  polish.
- `STOP_AND_DIAGNOSE` if tests fail or server/client command summary contracts
  contradict each other.

Closeout:
- verification complete:
  - UI tests pass
  - server tests pass
  - decision packet JSON parses
  - `git diff --check` passes
  - closeout resilience passes
  - staged-only closeout check passes
- commit:
  - required after staged verification
- push:
  - required by `DELIVERY_RULES.md` before contour is considered closed
- next contour:
  - choose the next narrow product-safe UI binding slice, or stop product-safe UI
    work if it would require live mutation
