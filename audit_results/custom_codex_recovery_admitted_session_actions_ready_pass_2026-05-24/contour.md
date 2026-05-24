<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Contour: CUSTOM_CODEX_RECOVERY_ADMITTED_SESSION_ACTIONS_READY_PASS

```text
CONTOUR: CUSTOM_CODEX_RECOVERY_ADMITTED_SESSION_ACTIONS_READY_PASS
Goal: expose a narrow machine packet and web workflow for already-admitted Codex Custom selected-session recovery actions.
Size: S
Risk level: medium
Decision owner: WBP control-layer canon
Mode: implementation + bounded browser proof

In scope:
- GET /api/codex/custom/recovery/admitted-session-actions
- server aggregation of the existing recovery contract and server-owned sessions packet
- UI rendering for admitted selected-session action readiness
- selected-session cancel via the existing session-manager endpoint
- owned-session-root cleanup via the existing session-manager endpoint
- tests, browser proof, independent audit, closeout

Out of scope:
- full recovery operator readiness
- rollback apply or rollback-point creation
- process discovery or process kill
- arbitrary path cleanup
- credential mutation, route removal, account login/reauth
- load/rotation proof rerun
- live prompt rerun
- desktop packaging or design polish

Assumptions:
- WBP remains the control layer.
- CLIProxyAPI remains the engine.
- The browser is a renderer/control surface and cannot provide backend, route, path, auth, token, secret, CODEX_HOME, or HOME.
- A selected session means a server-selected session from /api/codex/custom/sessions, not a browser-supplied filesystem target.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, AGENTS.md
- code: codex_recovery_contract.py, codex_custom_sessions.py, web_design_live_server.py, web_design_ui/index.html, web_design_ui/scripts/overview.js
- runtime evidence: browser proof on http://127.0.0.1:8792 with fixture command packets and production handler

Commands / files:
- wild_boar_proxy/codex_recovery_contract.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_recovery_contract.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py

Acceptance criteria:
- session_admitted_actions_ready is true only when readonly contract gates are ok and a valid server-selected owned session exists.
- selected_session_cancel_ready and owned_session_cleanup_ready are machine-visible.
- recovery_operator_ready, rollback_operator_ready, process_kill_operator_ready, rollback_claimed, and process_kill_claimed remain false.
- diagnostics_counted_as_recovery_action, readonly_checks_counted_as_mutation, and session_create_counted_as_recovery_action remain false.
- the new endpoint is GET-only and accepts no browser body.
- forbidden browser fields remain forbidden.
- dangerous actions stay visible-disabled or absent as executable controls.

Verification:
- tests: bundled Python unittest gates
- build: bundled node --check for overview.js
- manual: browser workflow proof
- live packet: admitted-session-actions packet before session, after create, after cancel, after cleanup

Artifacts:
- spec: audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/spec.md
- packet: audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/browser_proof.json
- closeout note: audit_results/custom_codex_recovery_admitted_session_actions_ready_pass_2026-05-24/closeout.md

Stop conditions:
- readonly source failure reported as success
- selected session absent but session_admitted_actions_ready=true
- rollback/process-kill/operator-ready overclaim
- browser can inject path/auth/backend/secret/CODEX_HOME/HOME
- GET route mutates runtime state
- tests fail from this contour

Closeout:
- verification complete: pending
- commit: pending
- push: pending
- next contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS, only after separate admitted rollback/process-owner contract
```
