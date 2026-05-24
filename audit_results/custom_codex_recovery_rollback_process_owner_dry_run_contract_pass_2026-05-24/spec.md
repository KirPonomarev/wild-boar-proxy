<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Rollback / Process Owner Dry-Run Contract

## Objective

Add a machine-readable dry-run contract for future Codex Custom rollback and process-owner recovery. The contract must define prerequisites and disabled dangerous actions without admitting live rollback, process kill, arbitrary cleanup, or full recovery operator readiness.

This contour intentionally includes a small control-layer packet, live-server GET route, and UI renderer because the product workflow is web-visible recovery readiness. The UI remains a renderer only; WBP server packets remain the truth source.

## In Scope

- Add `build_custom_recovery_rollback_process_owner_contract_packet`.
- Add `GET /api/codex/custom/recovery/rollback-process-owner-contract`.
- Render the packet in the existing Codex Custom Recovery panel.
- Extend recovery forbidden browser fields with `pid` and `process_id`.
- Show rollback/process-owner prerequisites:
  - rollback point required
  - rollback write surfaces required
  - rollback verification packet required
  - owned process identity required
  - current Codex process exclusion required
- Keep dangerous actions disabled.

## Out of Scope

- Rollback apply.
- Process kill.
- Rollback snapshot creation.
- Arbitrary path cleanup.
- Credential, account, or route mutation.
- Live prompt rerun.
- Load or rotation rerun.
- Desktop packaging.
- Design polish.
- Full recovery/operator-ready claim.

## Constraints

- WBP remains the control-layer recovery contract aggregator.
- `CodexCustomSessionManager` remains owner only for selected-session state, cancel, and owned-root cleanup.
- CLIProxyAPI remains engine, not recovery policy owner.
- Browser cannot send `backend_id`, `route_id`, `path`, `pid`, `process_id`, `token`, `auth`, `api_key`, `secret`, `CODEX_HOME`, or `HOME`.
- The new endpoint is GET-only and must not mutate runtime/session state.
- `rollback_live_ready`, `rollback_apply_admitted`, `process_kill_live_ready`, `process_kill_admitted`, and `recovery_operator_ready` must remain false.

## Assumptions

- Missing rollback point blocks live readiness, not dry-run contract definition.
- Missing owned process identity blocks live readiness, not dry-run contract definition.
- Current Codex process exclusion is required and remains unproven in this contour.
- Diagnostics remain a support artifact and are not counted as a recovery action.

## Acceptance Criteria

- [x] Packet exposes `claim_scope=custom_codex_recovery_rollback_process_owner_dry_run_contract_only`.
- [x] Packet exposes `rollback_contract_defined=true`.
- [x] Packet keeps `rollback_live_ready=false`.
- [x] Packet keeps `rollback_apply_admitted=false`.
- [x] Packet exposes `process_owner_contract_defined=true`.
- [x] Packet keeps `process_kill_live_ready=false`.
- [x] Packet keeps `process_kill_admitted=false`.
- [x] Packet keeps `recovery_operator_ready=false`.
- [x] Packet keeps `dangerous_actions_disabled=true`.
- [x] Packet keeps `browser_payload_allowed=false`.
- [x] No POST route exists for rollback, kill, cleanup-path, snapshot, or this contract endpoint.
- [x] UI renders the packet without claiming live readiness.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `python3 -B -m unittest tests.test_codex_recovery_contract tests.test_codex_custom_sessions tests.test_web_design_live_server tests.test_web_design_ui -q`
  - `python3 -B -m unittest tests.test_operator_surface tests.test_web_design_command_adapter -q`
- build:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - browser proof through the WBP web UI using production handler and fixture command packets
- live evidence:
  - `browser_proof.json`

## Open Questions

- None for this dry-run contract.
- A later rollback-point contour must define rollback point creation/verification before any live rollback claim is possible.
