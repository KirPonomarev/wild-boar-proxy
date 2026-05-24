# CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_PASS

CONTOUR:
Goal: Add a preflight-only process-kill readiness packet for a future stuck Codex Custom process recovery action.
Size: M
Risk level: high
Decision owner: canon
Mode: implementation + preflight proof

In scope:
- Add a contract-only process-kill preflight packet.
- Add `GET /api/codex/custom/recovery/process-kill/preflight`.
- Reject browser-supplied process/session/path/home/auth/backend/route fields before reading source truth.
- Use server-owned Custom session observation only.
- Surface the preflight in the web UI as read-only.
- Prove that no live kill route or process mutation exists in this contour.

Out of scope:
- Real process kill.
- Process termination primitives.
- Rollback execution.
- Full operator-ready recovery.
- Account rotation/load.
- CLIProxyAPI changes.
- Desktop packaging.

Assumptions:
- Existing admitted-session-actions packet remains the server-owned selected-session source.
- Actual process identity is not available for normal sessions yet; such sessions must block honestly with no process candidate.
- Eligible synthetic process observation is enough to prove the contract rules before a later live contour.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, DELIVERY_RULES.md, AGENTS.md.
- code: recovery contract, live server, web design UI, recovery tests.
- runtime evidence: unit and live-server endpoint packets.

Commands / files:
- `wild_boar_proxy/codex_recovery_contract.py`
- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_codex_recovery_contract.py`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`

Acceptance criteria:
- Browser selectors are rejected before source read.
- No POST or live process-kill route is added.
- No process termination primitive is added in the diff.
- Current and Original Codex candidates are rejected.
- Eligible packet keeps live-ready/admitted/claimed/performed false.
- Raw session id, pid, path, home, auth, token, backend, and route are not emitted in the preflight packet.

Verification:
- tests: 60 targeted tests, 238 recovery/session/live/UI tests, 33 operator/adapter tests.
- build: Python compile and JavaScript syntax check.
- manual: direct packet proof for eligible, injection rejection, and current Codex rejection.
- audit: independent auditor verdict pass with no findings.

Artifacts:
- spec: `spec.md`
- packets: `eligible_packet.json`, `browser_rejection_packet.json`, `current_codex_rejection_packet.json`
- report: `verification_summary.json`
- audit: `independent_audit.json`
- closeout: `closeout.md`

Stop conditions:
- Browser process or session selector is accepted.
- Raw process/session/home/auth material appears in the final packet.
- Any process kill primitive is introduced.
- UI exposes a live kill affordance.
- False-green appears for missing process candidate or protected Codex candidate.

Closeout:
- verification complete: yes
- commit: pending at artifact creation time
- push: pending at artifact creation time
- next contour: return to ACCOUNT_ROTATION_AND_MODERATE_LOAD_PASS unless recovery branch is explicitly continued
