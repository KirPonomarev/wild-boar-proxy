<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_PASS

```text
CONTOUR: CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_VERIFY_PASS
Goal: verify the newest server-owned Codex Custom rollback point without applying rollback.
Size: M
Risk level: high
Decision owner: canon
Mode: implementation + bounded live-proof

In scope:
- GET /api/codex/custom/recovery/rollback-point/verify.
- Server-owned artifact selection only.
- Schema, kind, timestamp, digest, manifest provenance, and write-surface checks.
- Browser-forbidden-field rejection.
- UI packet projection for the verify packet.
- Regression tests for false-green risks.

Out of scope:
- Rollback apply.
- Kill stuck process.
- Recovery/operator-ready claim.
- Arbitrary artifact/path/session selection.
- Desktop packaging or UI polish.

Assumptions:
- The rollback point create contour may write owned generated recovery artifacts.
- Verify may read only owned generated recovery artifacts.
- Provenance verification must compare the artifact against a server-side manifest, not the artifact alone.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md, AGENTS.md
- code: wild_boar_proxy/codex_recovery_contract.py, wild_boar_proxy/web_design_live_server.py, web UI overview
- runtime evidence: bounded local packet proof and unittest gates

Commands / files:
- wild_boar_proxy/codex_recovery_contract.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_recovery_contract.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py

Acceptance criteria:
- Verify returns ok only for the latest unambiguous server-owned rollback point with valid manifest provenance.
- Verify blocks browser artifact/path/digest/session input before filesystem read.
- Verify blocks tampered provenance, missing manifest, invalid timestamp, wrong surface, touch claims, and secret claims.
- Verify performs no filesystem write and admits no rollback apply.
- Packets redact artifact paths and keep current/original Codex untouched.

Verification:
- tests: py_compile, node --check, targeted recovery/server/UI tests, full recovery/session/live/UI tests, operator/adapter tests
- build: git diff --check
- manual: bounded local packet proof
- live packet: rollback_point_verify_packet.json

Artifacts:
- spec: spec.md
- packet: rollback_point_verify_packet.json
- closeout note: closeout.md

Stop conditions:
- current Codex touched
- Original Codex touched
- auth/secret material touched or leaked
- browser can choose artifact/path/digest/session
- verify succeeds without server-side manifest provenance
- rollback apply/operator-ready claim appears
- tests fail

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_PASS
```
