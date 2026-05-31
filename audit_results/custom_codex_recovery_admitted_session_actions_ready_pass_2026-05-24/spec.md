<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Codex Custom Admitted Session Recovery Actions

## Objective

Provide a narrow, machine-checkable readiness packet and web workflow for the two recovery actions already admitted by the Codex Custom recovery contract:

- stop the selected custom session through the session manager
- cleanup the selected owned temporary session root through the session manager

This contour intentionally mixes a small control-layer packet, live-server route, and web UI renderer because the accepted workflow is web-operated recovery for selected sessions. The mix is explicit and bounded: runtime truth stays in WBP packets; the UI only renders and triggers existing admitted session endpoints.

## In Scope

- Add `build_custom_recovery_admitted_session_actions_packet`.
- Add `GET /api/codex/custom/recovery/admitted-session-actions`.
- Render the packet in the existing Codex Custom Recovery panel.
- Keep using existing session-manager cancel and cleanup endpoints.
- Prove blocked-before-session, ready-after-session-create, safe cancel, safe cleanup, and blocked-after-cleanup states.

## Out of Scope

- Full recovery operator readiness.
- Rollback apply, rollback point creation, or rollback promotion.
- Process discovery or process kill.
- Arbitrary path cleanup.
- Credential mutation, route removal, account login/reauth.
- Load/rotation proof rerun.
- Live prompt rerun.
- Desktop packaging or design polish.

## Constraints

- WBP remains the control layer.
- CLIProxyAPI remains the engine.
- `CodexCustomSessionManager` remains the owner for cancel and owned cleanup semantics.
- The new readiness endpoint is read-only and must not mutate session state.
- Browser payload remains disallowed for the readiness endpoint.
- Browser must not provide `backend_id`, `route_id`, `path`, `token`, `auth`, `api_key`, `secret`, `CODEX_HOME`, or `HOME`.
- `recovery_operator_ready`, `rollback_operator_ready`, and `process_kill_operator_ready` must remain false.
- `diagnostics_counted_as_recovery_action`, `readonly_checks_counted_as_mutation`, and `session_create_counted_as_recovery_action` must remain false.

## Assumptions

- A "selected session" is selected by the server from the session list packet.
- A cleaned session is not ready for cancel or cleanup readiness.
- Readonly recovery contract failure blocks admitted-session readiness.
- Diagnostics remain a support artifact, not a recovery action.

## Acceptance Criteria

- [x] The packet returns `status=blocked`, `machine_error_code=ADMITTED_SESSION_ACTIONS_BLOCKED`, and `block_reason_code=SELECTED_SESSION_REQUIRED` when no server session exists.
- [x] The packet returns `status=ok`, `machine_error_code=ADMITTED_SESSION_ACTIONS_READY`, and `session_admitted_actions_ready=true` when readonly contract gates are ok and a valid server-owned session exists.
- [x] `selected_session_cancel_ready=true` and `owned_session_cleanup_ready=true` only under the same bounded readiness conditions.
- [x] Cleanup of a selected session returns `owned_session_root_only=true`, `arbitrary_path_accepted=false`, and `current_codex_home_touched=false`.
- [x] Cancel returns `process_kill_claimed=false`.
- [x] After cleanup, readiness returns blocked with `block_reason_code=SELECTED_SESSION_ALREADY_CLEANED`.
- [x] New endpoint has no POST handler.
- [x] UI renders the readiness packet without claiming operator, rollback, process-kill, load, rotation, or desktop readiness.

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

- None for this contour.
- Promotion to full rollback/operator-ready requires a separate contour with rollback-point and process-owner proof.
