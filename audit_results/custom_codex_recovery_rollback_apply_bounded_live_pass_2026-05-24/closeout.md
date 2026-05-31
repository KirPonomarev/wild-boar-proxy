# Closeout

## Contour Capsule

- goal: Perform the first bounded recovery apply as a WBP-owned receipt artifact only, without full rollback restore or operator-ready claims.
- head: pending commit from start `20d843af`
- touched files: `wild_boar_proxy/codex_recovery_contract.py`; `wild_boar_proxy/web_design_live_server.py`; `wild_boar_proxy/web_design_ui/index.html`; `wild_boar_proxy/web_design_ui/scripts/overview.js`; `tests/test_codex_recovery_contract.py`; `tests/test_web_design_live_server.py`; `tests/test_web_design_ui.py`; `audit_results/custom_codex_recovery_rollback_apply_bounded_live_pass_2026-05-24/*`
- tests run: python py_compile; node --check; 43 targeted recovery/live/UI tests; 219 recovery/session/live/UI tests; 33 operator/adapter tests; git diff --check; closeout resilience; scoped redaction scan
- blocked risks: no current Codex touch; no Original Codex touch; no auth/account/API credential mutation; no process kill; no full rollback restore claim; no recovery/operator-ready claim; browser forbidden fields rejected before read/write; hidden manifest write removed after audit
- next exact command: `git status -sb --untracked-files=no`
- resume from here: `CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS`
- Contour: `CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PASS`
- Branch: `codex/external-agent-lab-isolated`
- Start HEAD: `20d843af`
- Result token: `CUSTOM_CODEX_RECOVERY_ROLLBACK_APPLY_BOUNDED_LIVE_PERFORMED`
- Next contour: `CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS`

## What Changed

- Added bounded rollback apply receipt builder.
- Added `POST /api/codex/custom/recovery/rollback-apply`.
- Added WBP web recovery packet projection and action button.
- Added contract, live server, and UI regression tests.
- Recorded first failed audit, fix, second passing audit, and machine proof.

## Runtime Truth

- Successful bounded apply writes exactly one receipt artifact.
- `rollback_apply_completed_scope=bounded_apply_receipt_only`.
- `rollback_completed=true` means receipt completion only.
- `rollback_live_ready=false`.
- `recovery_operator_ready=false`.
- `process_kill_performed=false`.
- Current Codex, Original Codex, Codex home, auth material, and secrets remain untouched.
- Browser-forbidden payload path is blocked with no read and no write.

## Verification

- `python3 -m py_compile wild_boar_proxy/codex_recovery_contract.py wild_boar_proxy/web_design_live_server.py`
- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- `$BUNDLED_PYTHON -B -m unittest tests.test_codex_recovery_contract tests.test_web_design_live_server.WebDesignCodexCustomSessionEndpointTests.test_codex_custom_recovery_rollback_point_create_admission_endpoint_allows_bounded_create tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_recovery_surface_is_bounded_and_readonly -q`
- `$BUNDLED_PYTHON -B -m unittest tests.test_codex_recovery_contract tests.test_codex_custom_sessions tests.test_web_design_live_server tests.test_web_design_ui -q`
- `$BUNDLED_PYTHON -B -m unittest tests.test_operator_surface tests.test_web_design_command_adapter -q`

## Independent Audit

First auditor: `Ohm`, model `gpt-5.4-mini`

Verdict: fail

Finding: hidden second manifest write under `bounded_apply_receipt_only`.

Fix: removed receipt manifest write and added regression assertion.

Second auditor: `Planck`, model `gpt-5.4-mini`

Verdict: pass

Findings: none

## Scope Check

No full rollback restore, process kill, auth mutation, account mutation, API credential mutation, current Codex mutation, Original Codex mutation, or recovery/operator-ready claim was added.

## Resume From Here

Resume from `CUSTOM_CODEX_RECOVERY_APPLY_RECEIPT_VERIFY_PASS`.

First command:

```bash
git status -sb --untracked-files=no
```

Then inspect:

```bash
python3 -m unittest tests.test_codex_recovery_contract -q
```
