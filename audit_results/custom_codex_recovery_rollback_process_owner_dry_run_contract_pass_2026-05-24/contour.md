<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT_PASS

```text
CONTOUR: CUSTOM_CODEX_RECOVERY_ROLLBACK_PROCESS_OWNER_DRY_RUN_CONTRACT_PASS
Goal: define a dry-run-only rollback/process-owner recovery contract without admitting live rollback, process kill, or full recovery operator readiness.
Size: S
Risk level: medium
Decision owner: WBP control-layer canon
Mode: implementation + bounded browser proof

In scope:
- GET /api/codex/custom/recovery/rollback-process-owner-contract
- server-issued rollback/process-owner prerequisite matrix
- UI rendering of the dry-run contract
- disabled dangerous recovery controls with machine reason fields
- tests, browser proof, independent audit, closeout

Out of scope:
- real rollback apply
- real process kill
- rollback snapshot creation
- arbitrary path cleanup
- credential, account, or route mutation
- live prompt rerun
- load or rotation rerun
- desktop packaging or design polish
- CUSTOM_CODEX_RECOVERY_ROLLBACK_AND_OPERATOR_READY_PASS claim
- CUSTOM_CODEX_RECOVERY_OPERATOR_READY claim
- EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY claim

Assumptions:
- WBP remains the control-layer recovery contract owner.
- CLIProxyAPI remains the engine and does not own recovery policy.
- The browser is a renderer/control surface, not a truth source.
- Existing selected-session cancel and owned cleanup remain the only admitted recovery mutations.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, AGENTS.md
- code: codex_recovery_contract.py, web_design_live_server.py, web_design_ui/index.html, web_design_ui/scripts/overview.js
- runtime evidence: browser proof on http://127.0.0.1:8793 with fixture command packets and production handler

Commands / files:
- wild_boar_proxy/codex_recovery_contract.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_recovery_contract.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py

Acceptance criteria:
- rollback_contract_defined=true while rollback_live_ready=false
- rollback_apply_admitted=false
- process_owner_contract_defined=true while process_kill_live_ready=false
- process_kill_admitted=false
- recovery_operator_ready=false
- browser_payload_allowed=false
- forbidden browser fields include path, pid, process_id, backend/auth/secret, CODEX_HOME, and HOME
- no POST mutation endpoint exists for rollback, kill, cleanup-path, snapshot, or the new contract endpoint
- missing rollback point blocks live readiness without blocking dry-run contract definition
- current Codex process exclusion is required and not treated as proven

Verification:
- tests: bundled Python unittest gates
- build: bundled node --check for overview.js
- manual: browser workflow proof
- live packet: rollback/process owner dry-run packet from web UI

Artifacts:
- spec: audit_results/custom_codex_recovery_rollback_process_owner_dry_run_contract_pass_2026-05-24/spec.md
- packet: audit_results/custom_codex_recovery_rollback_process_owner_dry_run_contract_pass_2026-05-24/browser_proof.json
- closeout note: audit_results/custom_codex_recovery_rollback_process_owner_dry_run_contract_pass_2026-05-24/closeout.md

Stop conditions:
- recovery_operator_ready=true
- rollback_live_ready=true
- rollback_apply_admitted=true
- process_kill_live_ready=true
- process_kill_admitted=true
- browser can pass path or pid into a recovery action
- current Codex process/root is treated as candidate
- a mutation endpoint appears
- UI computes primary readiness locally
- tests fail from this contour

Closeout:
- verification complete: pending
- commit: pending
- push: pending
- next contour: CUSTOM_CODEX_RECOVERY_ROLLBACK_POINT_DRY_RUN_PASS
```
