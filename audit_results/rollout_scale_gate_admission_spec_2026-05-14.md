<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Rollout Scale Gate Admission Spec

## Objective

Audit the pre-desktop web UI and action boundary for rollout/scale claim safety.
This contour does not implement a rollout screen, does not execute live rollout,
and does not grant desktop admission.

## In Scope

- Verify current web UI has no active rollout-stage mutation controls.
- Verify browser actions cannot pass raw `command_id`, raw argv, or arbitrary
  rollout commands.
- Verify current copy does not claim `STABLE_20_PROVED`, `SCALE_COMPLETE`,
  `PILOT_READY`, or production readiness.
- Classify rollout and scale command surfaces as allowed, deferred, owner/live
  only, or forbidden for future UI work.
- Preserve the current canon fact: 16-account evidence is observed-only and does
  not prove 20-account scale.

## Out of Scope

- No new rollout UI screen.
- No visual design transfer.
- No desktop renderer work.
- No live rollout execution.
- No `policy stage set`.
- No `rollout stage prove`.
- No `rollout stage advance`.
- No execution-core changes.
- No `runtime.py` changes.
- No direct raw evidence/log/state file reads.

## Constraints

- `rollout rotation inspect --json` is a bounded read surface only.
- `policy stage set <10|15|20> --json` is an owner mutation surface and must not
  be exposed as an active web UI action in this contour.
- `rollout evidence capture 16 --json` may produce only
  `field_evidence_observed_only`.
- `READY_FOR_STAGE_ADVANCE` is posture compatibility only, not stage proof.
- Desktop remains owner-gated because `desktop_approval_granted` is false in
  the next-contour queue.

## Acceptance Criteria

- [x] Current UI/action boundary scan finds no active rollout mutation controls.
- [x] Current UI/action boundary rejects raw `command_id` browser actions.
- [x] Current UI/action boundary rejects unsupported browser payload fields.
- [x] Current command adapter remains allowlist-based.
- [x] Forbidden scale/pilot/stable claims are classified.
- [x] Claim admission is blocked unless future machine-carried evidence and
  owner approval exist.
- [x] No product code changes are required for this admission contour.

## Verification

- static scan: PASS
- web/action boundary audit: PASS
- canon/claim admission audit: BLOCKED for scale promotion, as expected
- tests: required before closeout

## Open Questions

- None for this contour. Future rollout UI design must start from the admission
  matrix in this packet and remain owner-gated for live scale commands.
