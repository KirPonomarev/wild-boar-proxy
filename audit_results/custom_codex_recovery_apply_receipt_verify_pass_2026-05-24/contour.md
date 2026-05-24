<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS

CONTOUR:
Goal: prove a read-only verifier for the latest server-owned bounded rollback apply receipt.
Size: M
Risk level: high
Decision owner: operator canon
Mode: implementation + live-proof

In scope:
- Add a read-only contract packet for rollback apply receipt verification.
- Add a server GET endpoint for receipt verify.
- Project the packet into the existing web recovery surface.
- Reject browser/query selectors before reading artifacts.
- Verify digest, provenance, source preflight, and rollback-point reference.
- Prove no write, no apply, no process kill, no operator-ready claim, and no current/original Codex touch.

Out of scope:
- System recovery readiness.
- Rollback execution beyond the existing bounded apply receipt writer.
- Stop/cleanup/kill stuck process.
- Desktop packaging or rich UI polish.

Assumptions:
- The previous contour may create server-owned rollback point and bounded apply receipt artifacts.
- Old receipts without embedded source preflight are not accepted as provenance-verified receipts.
- Browser cannot choose receipt path, digest, account, backend, session, auth, or runtime home.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md, AGENTS.md
- code: codex_recovery_contract.py, web_design_live_server.py, web_design_ui, recovery tests
- runtime evidence: targeted unit tests, full recovery/session/UI tests, machine proof packet, independent audit

Commands / files:
- wild_boar_proxy/codex_recovery_contract.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_recovery_contract.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py

Acceptance criteria:
- Success packet reports verified_scope=bounded_apply_receipt_only.
- Success packet reports human_summary="receipt verified · not system recovery".
- Success packet reports receipt_payload_digest_verified=true and receipt_provenance_verified=true.
- Success and failure packets keep filesystem_write_performed=false.
- Success and failure packets keep rollback_apply_performed=false, process_kill_performed=false, recovery_operator_ready=false.
- Browser forbidden fields, including blank query values, block before filesystem read.
- Forged receipt provenance blocks verification.

Verification:
- tests: targeted recovery verifier tests, web endpoint/UI tests, full recovery/session/live/UI suite, operator/adapter suite
- build: Python compile and node --check
- manual: independent auditor passed after forged-provenance and blank-query fixes
- live packet: receipt_verify_packet.json and browser_rejection_packet.json

Artifacts:
- spec: spec.md
- packet: receipt_verify_packet.json
- closeout note: closeout.md

Stop conditions:
- Any write/apply/kill/operator-ready flag true on verify.
- Any current/original Codex or auth material touch.
- Any browser field accepted as selector.
- Any forged digest/provenance accepted as verified.
- Any ambiguous latest receipt accepted.

Closeout:
- verification complete: yes
- commit: pending at artifact creation
- push: pending at artifact creation
- next contour: CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_PASS
