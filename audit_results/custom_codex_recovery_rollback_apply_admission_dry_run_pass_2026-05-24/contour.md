<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_DRY_RUN_PASS

```text
CONTOUR: CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_ADMISSION_DRY_RUN_PASS
Goal: evaluate future rollback-apply admission without admitting or performing rollback.
Size: M
Risk level: high
Decision owner: canon
Mode: implementation + dry-run proof

In scope:
- Read-only builder for rollback apply admission dry-run.
- GET /api/codex/custom/recovery/rollback-apply/admission-dry-run.
- UI projection of dry-run admission packet.
- Regression tests for browser field injection, missing verify, touch/secret blockers, no write, no apply, no process kill.
- Independent audit for false-green and layer mixing.

Out of scope:
- Live rollback apply.
- Cleanup/cancel/kill.
- Runtime/session mutation.
- Operator-ready recovery claim.
- CLIProxyAPI engine work.
- Desktop packaging or UI polish.

Assumptions:
- Rollback point create and verify are already proven by prior contours.
- Verified rollback point is prerequisite evidence, not apply permission.
- This contour may evaluate eligibility for a future contour while keeping all live flags false.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md, AGENTS.md
- code: recovery contract, web live server, web UI overview, recovery tests
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
- Admission dry-run succeeds only after valid rollback point verify, recovery contract, process owner contract, session state readout, and eligible write-surface metadata.
- Admission dry-run rejects browser-supplied artifact/path/digest/session/backend/route/home/auth/token fields.
- Admission dry-run performs no filesystem read/write and no process kill.
- Admission dry-run keeps rollback apply admitted/ready/performed/completed false.
- Admission dry-run keeps current Codex, Original Codex, auth, and secret touch claims false.
- UI uses GET fetch projection only and fallback stays blocked.

Verification:
- tests: py_compile, node --check, targeted recovery/server/UI, full recovery/session/live/UI, operator/adapter
- build: git diff --check
- manual: bounded local packet proof
- audit: independent auditor returned no findings

Artifacts:
- spec: spec.md
- packet: rollback_apply_admission_dry_run_packet.json
- closeout note: closeout.md

Stop conditions:
- rollback_apply_admitted/ready/performed/completed becomes true
- filesystem write or process kill appears in dry-run packet
- browser field injection reaches server-owned verify/read path
- current/original Codex or auth/secret touch appears
- UI shows green without machine packet proof
- tests fail

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_LIVE_ADMISSION_PASS
```
