<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# PLAN_RECENTER_TO_PRODUCT_WORK Contour

CONTOUR:
PLAN_RECENTER_TO_PRODUCT_WORK

Goal:
Recenter the active plan so product-safe UI work can resume without claiming
that the runtime/live-action chain is repaired or closed.

Size:
S

Risk level:
medium

Decision owner:
Maintainer for planning and document truth. Operator-owned live-runtime
mutations are out of scope.

Mode:
implementation, docs-only

In scope:
- Update the top active planning section in `MASTER_PLAN.md`.
- Preserve current runtime truth: selector/live-action chain remains blocked
  and parked.
- Explicitly allow separate product-safe work:
  `UI_READONLY_COMMAND_BINDING_PASS`.
- Limit that UI lane to read-only JSON command binding, truth display, command
  ledger/history display, and disabled live-action reasons.
- State that this is not rich UI expansion, not design polish, and not
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.
- Create a small decision packet and closeout under
  `audit_results/plan_recenter_to_product_work_2026-05-16/`.

Out of scope:
- No UI implementation.
- No design polish.
- No live runtime mutation.
- No `sync --json` retry.
- No `launch smoke --json`.
- No `stable repair --apply --json`.
- No sandbox `auth.json` materialization.
- No onboarding rerun.
- No exact auth-source admission.
- No stage/pilot/20-account proof claim.
- No attempt to resolve `LOCK_HELD` or runtime regression in this contour.

Assumptions:
- `CANON.md` remains the highest product/runtime authority after `AGENTS.md`.
- `MASTER_PLAN.md` may be updated to clarify active lane separation.
- Product-safe UI work can proceed if it does not claim runtime repair, does
  not perform live mutation, and does not show false-green state.
- Runtime/live-action work remains parked until a separate diagnose/repair
  contour addresses repeated `LOCK_HELD` and post-retry runtime regression.

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
  - `WORKFLOW_OS_V1_2.md`
- code:
  - none required
- runtime evidence:
  - existing committed audit packets only
  - no fresh live packets in this contour

Commands / files:
- Read:
  - `MASTER_PLAN.md`
  - `CANON.md`
  - `DELIVERY_RULES.md`
- Write:
  - `MASTER_PLAN.md`
  - `audit_results/plan_recenter_to_product_work_2026-05-16/contour.md`
  - `audit_results/plan_recenter_to_product_work_2026-05-16/decision_packet.json`
  - `audit_results/plan_recenter_to_product_work_2026-05-16/closeout.md`

Acceptance criteria:
- `MASTER_PLAN.md` clearly separates:
  - runtime/live-action chain: blocked/parked
  - product-safe UI lane: allowed under read-only + disabled-action constraints
- The next product-safe contour is named:
  `UI_READONLY_COMMAND_BINDING_PASS`.
- The plan does not claim:
  - execution core closed
  - design gate ready
  - exact auth-source readiness
  - selector refresh success
  - onboarding readiness
  - pilot/stage readiness
- All live-mutating actions remain explicitly parked.
- The wording follows canon order and does not override runtime truth.

Verification:
- tests:
  - not applicable; docs-only contour
- build:
  - `git diff --check`
- manual:
  - confirm `MASTER_PLAN.md` top section contains lane separation
  - confirm no runtime/private data is added
  - confirm no UI implementation is included
- live packet:
  - none; live commands are out of scope

Artifacts:
- spec:
  - `audit_results/plan_recenter_to_product_work_2026-05-16/contour.md`
- packet:
  - `audit_results/plan_recenter_to_product_work_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/plan_recenter_to_product_work_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if `MASTER_PLAN.md` or `CANON.md` is found to forbid even
  read-only UI command binding before runtime repair closes.
- `STOP_AND_DIAGNOSE` if the planned wording would imply
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`.
- `STOP_AND_DIAGNOSE` if the contour requires any fresh live command to justify
  the docs change.
- `STOP_AND_DIAGNOSE` if runtime and product lanes cannot be separated without
  contradicting canon.

Closeout:
- verification complete:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/plan_recenter_to_product_work_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- commit:
  - required if changes are made
- push:
  - required by `DELIVERY_RULES.md` for closed contours
- next contour:
  - `UI_READONLY_COMMAND_BINDING_PASS`
