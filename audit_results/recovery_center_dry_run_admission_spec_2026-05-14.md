<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Recovery Center Dry Run Admission Spec

## Contour

`RECOVERY_CENTER_DRY_RUN_ADMISSION`

## Goal

Decide whether a bounded dry-run recovery result surface may be admitted into
the web design UI, and define the narrowest truthful product contract.

## Final verdict

`RECOVERY_CENTER_DRY_RUN_SUMMARY_ONLY_ADMITTED`

## Why this verdict

The repo already contains an admitted, allowlisted dry-run action:

- `stable_repair_plan` maps to `stable repair --dry-run --json`
- the action is explicitly non-mutating
- the action is explicitly framed as recovery planning only
- browser payload remains `ui_action` only

But the richer "Recovery center" screen in the design package asks for more
than the current safe surface truthfully provides. The existing dry-run command
packet contains path-rich `transaction_plan` details such as `auth_ref`,
approved target inventory references, and basename-collision internals.
Those details are not admitted as a browser-owned recovery model in this
contour.

So the contour admits:

- bounded command-result summary only

and does not admit:

- a detailed recovery-plan viewer
- target/strategy/policy selection
- rollback-note truth
- apply semantics
- persistent recovery state in UI

## Canon anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI / command packets remain truth owners.
- UI is not a recovery engine.
- UI is not a repair planner.
- UI is not a log parser.
- UI is not a generic repair console.
- Dry-run truth must remain a single command-result surface, not a persistent
  UI-owned recovery model.
- Browser must not choose recovery strategy, recovery target, or repair policy
  unless already admitted by a bounded packet.
- Dry-run output must not be normalized into a multi-step UI plan.
- Dry-run must never imply apply, success, readiness, or rollback safety.

## Repo facts

1. `UI_READINESS_SPEC.md` already admits `Stable Repair Dry Run` as an existing
   UI action bound to `stable repair --dry-run --json`, with note
   `Non-mutating recovery planning surface.` It also states that stable repair
   dry run is preferred before stable repair apply.

2. `wild_boar_proxy/web_design_command_adapter.py` already allowlists
   `stable_repair_dry_run`.

3. `wild_boar_proxy/web_design_live_server.py` already allowlists
   `stable_repair_plan` with:
   - `action_role = recovery_planning`
   - `mutates_runtime = False`
   - `affects_primary_truth = False`
   - claim scope: `только dry-run план восстановления`

4. `tests/test_web_design_live_server.py` confirms:
   - `stable_repair_plan` is accepted by the UI action endpoint
   - `stable_repair_apply` is blocked as `UI_ACTION_NOT_ALLOWED`

5. `tests/test_web_design_ui.py` confirms:
   - `stable_repair_plan` is present
   - `stable_repair_apply` is absent from the web design UI

6. The current live-server `_action_result(...)` returns only bounded top-level
   command-result fields plus optional `packet.data`. The stable repair dry-run
   packet does not expose a separate browser-safe `data` subsection, so the
   browser-facing result remains summary-only.

7. `wild_boar_proxy/runtime.py` shows that the dry-run command packet contains
   a `transaction_plan` with path-rich and authority-rich internals, including:
   - `registry_source_inputs.eligible_registry_auth_refs[*].auth_ref`
   - `source_copy_missing_auth_refs[*].auth_ref`
   - `source_copy_basename_collisions[*].auth_refs`
   - approved repair target references and mutation-authority detail

8. `tests/test_cli.py` confirms:
   - dry-run exposes `transaction_plan`
   - dry-run does not leak into unrelated JSON surfaces such as
     `status --json`, `healthcheck --json`, `accounts list --json`

9. `audit_results/ui_final_screen_passports_2026-05-14.json` and
   `audit_results/ui_final_render_package_completeness_matrix_2026-05-14.json`
   already classify `27_recovery_center` as `admission-required` with note:
   `Dry-run planning exists; apply-like recovery center actions remain deferred/admission-required.`

## Admitted now

The current web contour truthfully admits only this bounded dry-run recovery
surface:

- top-level command-result summary from `stable repair --dry-run --json`
  including:
  - `status`
  - `human_message`
  - `machine_error_code`
  - `next_action`
  - `changed_files`
  - non-mutating action metadata

Optional UI copy may say:

- dry-run result
- advisory summary
- operator review required
- unavailable
- stale
- historical

## Not admitted in this contour

- full `transaction_plan` rendering in browser
- registry-source path detail
- approved repair-target path detail
- basename-collision detail as a browser recovery model
- file-level mutation preview UI
- recovery target selection
- recovery strategy selection
- repair policy selection
- repair apply
- rollback promises
- "safe to apply" claims
- persistent recovery-center state

## Packet boundary

Allowed future browser payload in the currently admitted shape:

- `ui_action`

Not allowed:

- `command_id`
- `argv`
- `shell`
- arbitrary flags
- path
- token
- secret
- recovery strategy selector
- recovery target selector
- repair policy selector

## Copy rules

UI may say:

- dry-run result
- advisory summary
- operator review required
- unavailable
- stale
- historical

UI must not say:

- fixed
- recovered
- healthy
- safe now
- safe to apply
- recommended fix
- auto-repair ready
- rollback guaranteed
- applied
- verified

## Implication for later work

If a future contour wants a real Recovery Center screen rather than the current
bounded summary action, it needs a stricter dedicated packet boundary for
browser-safe plan detail. That future packet must avoid browser-owned path,
policy, or authority semantics and must preserve hard separation between
dry-run and apply.

## Identity preservation check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.
