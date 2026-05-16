<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_READONLY_LANE_EXIT_SUMMARY_PASS Contour

CONTOUR:
UI_READONLY_LANE_EXIT_SUMMARY_PASS

Goal:
Create a compact exit summary for the product-safe UI-readonly lane. The summary
must explain what is currently known, what remains blocked, what is safe to do
inside the UI, what is forbidden, and why the next real contour must move back
to runtime diagnosis instead of another UI panel.

Size:
S

Risk level:
medium

Decision owner:
Maintainer for UI/control-layer implementation. Canon owns disputed runtime
truth interpretation. Operator owns live mutation, which is out of scope.

Mode:
implementation, product-safe / read-only UI lane closeout

Why this contour:
`MASTER_PLAN.md` allows the product-safe UI lane only for read-only truth
display, command ledger/history display, and disabled live-action reasons.
Those slices are already implemented. This contour closes the UI-readonly lane
with a compact handoff summary and prevents further UI panel churn.

In scope:
- Add a compact UI-readonly lane exit summary.
- Use only:
  - static canon-backed blocker facts from `MASTER_PLAN.md` and `CANON.md`
  - current UI source state already present in the page
  - existing disabled action metadata/reasons
  - existing snapshot command ledger state
- Show:
  - current UI truth source
  - that runtime/live-action chain remains parked
  - blocker family and no-progress handoff reasons
  - safe current scope for read-only inspection
  - forbidden current scope until runtime diagnosis closes the parked chain
  - next honest contour as text only:
    `STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION`
- Keep the summary display-only.
- Add focused UI tests against false-green and scope drift.
- Add contour artifacts and closeout.

Out of scope:
- No new endpoints.
- No new command execution.
- No live runtime commands.
- No polling.
- No persistence/history.
- No runtime repair.
- No selector retry.
- No auth materialization.
- No onboarding mutation.
- No route mutation.
- No stage proof or rollout readiness claim.
- No design polish.
- No rich UI expansion.
- No new product flow.
- No button/action that starts the recommended next contour.
- No claim of `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.
- No claim that UI-readonly work fixes runtime/live-action truth.

Assumptions:
- `MASTER_PLAN.md` currently parks runtime/live-action work on repeated selector
  lock contention and post-retry runtime regression.
- `UI_READONLY_COMMAND_BINDING_PASS` closed disabled live-action reason binding.
- `UI_READONLY_COMMAND_SNAPSHOT_LEDGER_PASS` closed bounded snapshot command
  summary display.
- The remaining useful UI-readonly work is an exit/handoff summary, not another
  product panel.
- If this contour requires fresh runtime truth, new command execution, or live
  mutation, the contour must stop.

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
  - `WORKFLOW_OS_V1_2.md`
- code:
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_ui.py`
- prior contour evidence:
  - `audit_results/ui_readonly_command_binding_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_command_snapshot_ledger_pass_2026-05-16/decision_packet.json`
- runtime evidence:
  - no fresh live runtime packets required
  - no live mutation authorized or needed

Commands / files:
- Read:
  - `MASTER_PLAN.md`
  - `CANON.md`
  - current UI source/metadata/ledger code paths
  - existing UI tests
- Write:
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_ui.py`
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/contour.md`
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/decision_packet.json`
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/closeout.md`

Acceptance criteria:
- UI shows a compact product-safe UI-readonly lane exit summary.
- Summary clearly says runtime/live-action chain remains parked.
- Summary distinguishes:
  - allowed read-only UI inspection
  - blocked live mutation/runtime repair
  - next runtime diagnosis contour
- Summary points to
  `STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION` as text only.
- Summary does not expose a button/action to start runtime diagnosis.
- Summary does not fetch new data or run commands.
- Summary does not persist history.
- Summary does not show rollout/stage/auth/onboarding/runtime readiness.
- Summary does not turn read-only ok, command ok, or disabled metadata into
  runtime-green.
- Existing disabled action metadata and snapshot command ledger behavior remain
  unchanged.
- No raw packet/private/runtime data is rendered.
- UI-readonly lane is considered product-sufficient after this contour unless
  tests reveal a defect.

Verification:
- tests:
  - `python3 -m unittest -q tests.test_web_design_ui`
  - `python3 -m unittest -q tests.test_web_design_live_server`
- build:
  - `python3 -m json.tool audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
- manual:
  - inspect that no new fetch/api/action path was added
  - inspect that the recommended next contour is text only
  - inspect that summary uses current UI state and existing metadata/ledger only
  - inspect that no false-green readiness claim appears
  - inspect that UI-readonly lane is not extended into another panel chain
- live packet:
  - none; live commands are out of scope

Artifacts:
- spec:
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/ui_readonly_lane_exit_summary_pass_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if implementation requires fresh live runtime data.
- `STOP_AND_DIAGNOSE` if implementation requires new command execution.
- `STOP_AND_DIAGNOSE` if a recommended next contour becomes a UI action/button.
- `STOP_AND_DIAGNOSE` if the summary starts diagnosing or repairing runtime.
- `STOP_AND_DIAGNOSE` if the work drifts into design polish or rich UI
  expansion.
- `STOP_AND_DIAGNOSE` if the summary claims readiness instead of blocked truth.
- `STOP_AND_DIAGNOSE` if tests reveal stale-green or false-green behavior.
- `STOP_AND_DIAGNOSE` if raw/private/runtime data can render.

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
  - `STOP_AND_DIAGNOSE_REPEATED_SELECTOR_LOCK_AND_RUNTIME_REGRESSION`
- final closeout note must explicitly say:
  - product-safe UI-readonly lane is product-sufficient for now
  - next work should move to runtime diagnosis, not another UI-readonly panel
