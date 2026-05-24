<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS

CONTOUR:
Goal: prove a read-only stop/cleanup preflight for server-owned Codex Custom sessions.
Size: M
Risk level: high
Decision owner: operator canon
Mode: implementation + proof

In scope:
- Add a preflight-only packet derived from admitted session action truth.
- Add GET `/api/codex/custom/recovery/stop-cleanup/preflight`.
- Add minimal web projection for stop/cleanup preflight.
- Reject browser selectors before session read/action.
- Prove no cancel, cleanup, process kill, rollback live, operator ready, or filesystem write.

Out of scope:
- Live stop.
- Live owned cleanup.
- Process kill.
- Arbitrary path cleanup.
- System recovery/operator-ready claim.
- UI redesign.

Assumptions:
- `/api/codex/custom/recovery/admitted-session-actions` remains the source packet for selected-session readiness.
- Browser does not select session id, path, process id, backend, auth, or artifacts.
- A cleaned session blocks preflight honestly.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, COMMAND_API.md, AGENTS.md
- code: recovery contract, live server, web UI, recovery/session tests
- runtime evidence: targeted tests, full bundled-python suite, independent audit

Commands / files:
- wild_boar_proxy/codex_recovery_contract.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_recovery_contract.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py

Acceptance criteria:
- Success reports `CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY`.
- Success reports `verified_scope=owned_custom_session_stop_cleanup_preflight_only`.
- Success is derived from `/api/codex/custom/recovery/admitted-session-actions`.
- Browser forbidden fields, including blank values, block before read.
- Raw selected session id is not emitted by the preflight packet.
- Success and failure packets keep cancel/cleanup/kill/write/operator/rollback-live flags false.
- Ambiguous latest server-side session selection blocks readiness.

Verification:
- tests: recovery contract tests, web endpoint/UI tests, full bundled suite
- build: Python compile and JavaScript syntax check
- manual: independent audit pass
- live packet: preflight_ready_packet.json and browser_rejection_packet.json

Artifacts:
- spec: spec.md
- packet: preflight_ready_packet.json
- closeout note: closeout.md

Stop conditions:
- Any `cancel_packet`, `cleanup_packet`, filesystem delete, or process kill in preflight.
- Browser `session_id`, `path`, `pid`, `backend_id`, or auth selector accepted.
- Raw selected session id leaks in preflight packet.
- Operator-ready, rollback-live, or process-kill readiness becomes true.
- Existing `admitted-session-actions` truth is duplicated instead of consumed.

Closeout:
- verification complete: yes
- commit: pending at artifact creation
- push: pending at artifact creation
- next contour: CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_PASS
