<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Stable Policy Drift Operational Normalization Plan

CONTOUR_ID: STABLE_POLICY_DRIFT_OPERATIONAL_NORMALIZATION
CONTOUR_CLASS: LIVE_OPERATION_DECLARATION_PLUS_BOUNDED_OPERATIONAL_NORMALIZATION
CONTOUR_STATUS: CLOSED_PRECONDITION_NOT_MET

## Goal

Normalize operational `STABLE_POLICY_DRIFT` through canonical owner commands,
then prove with fresh owner packets whether a later gate recheck may open.

## Canon Basis

- `CANON.md` requires explicit live-thread authorization for live runtime
  mutations.
- `AGENTS.md` requires declared write surfaces and rollback expectations for
  real-path mutations.
- `COMMAND_API.md` keeps `stable repair --dry-run --json` non-mutating.
- `COMMAND_API.md` bounds `stable repair --apply --json` to approved target
  inventory mutation.
- `COMMAND_API.md` keeps stable-runtime activation evidence under
  `launch smoke --json`.

## Execution Result

Only Phase 0 read-only preflight was executed.

No apply command ran because authorization was not present in the active thread
under the exact canon rule.

## Intended Next Step

If the operator wants this live operation to proceed, the next contour can reuse
this Phase 0 result only after explicit authorization is present and a fresh
preflight confirms the dry-run still matches the same bounded shape.
