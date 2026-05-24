# CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_LIVE_PASS

CONTOUR:
Goal: Add a bounded web-triggered Custom Codex recovery action that cancels and cleans one server-selected owned custom session after a fresh preflight.
Size: M
Risk level: high
Decision owner: canon
Mode: implementation + live-proof

In scope:
- Add server endpoint `POST /api/codex/custom/recovery/stop-cleanup`.
- Reject any browser-supplied selector, path, auth, token, process, or home fields before mutation.
- Require fresh stop-cleanup preflight and same selected session ref before lifecycle mutation.
- Cancel the server-selected custom session before cleanup.
- Cleanup only the owned temporary custom session root.
- Expose a redacted live packet to the web UI.
- Add regression tests, machine proof packets, independent audit, closeout, commit, and push.

Out of scope:
- Process kill readiness.
- Full operator recovery readiness.
- Rollback execution.
- Original Codex launch or mutation.
- Account rotation, load, route credential mutation, or desktop packaging.

Assumptions:
- Existing `codex_custom_sessions.cancel_packet` and `cleanup_packet` are the lifecycle mutation primitives for this contour.
- The web UI may invoke the action, but server-side contract code remains the policy source.
- A selected session is represented externally by a redacted session ref, not a raw session id.

Inputs:
- docs: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, COMMAND_API.md, DELIVERY_RULES.md, AGENTS.md.
- code: `wild_boar_proxy/codex_recovery_contract.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/`.
- runtime evidence: unit packets and live-server endpoint regression tests.

Commands / files:
- `wild_boar_proxy/codex_recovery_contract.py`
- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_codex_recovery_contract.py`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`

Acceptance criteria:
- Browser forbidden fields are blocked before cancel or cleanup.
- Preflight is required and must be ready.
- The selected session ref cannot change between preflight and live mutation.
- Cancel failure does not proceed to cleanup.
- Cleanup failure after cancel is not reported as green.
- Success proves cancel verified, cleanup verified, owned root only, and no process kill claim.
- Final live packet omits raw session id, filesystem path, backend id, and auth material.

Verification:
- tests: contract, session, live-server, UI, operator-surface, command-adapter.
- build: Python compile and JavaScript syntax check.
- manual: direct packet proof for success, rejection, race block, and partial cleanup failure.
- live packet: `live_ready_packet.json`.

Artifacts:
- spec: `spec.md`
- packet: `live_ready_packet.json`
- report: `verification_summary.json`
- audit: `independent_audit.json`
- closeout note: `closeout.md`

Stop conditions:
- Browser can supply a raw session id, path, auth, token, home, or process selector.
- Current Codex or Original Codex is touched.
- Cleanup accepts arbitrary paths.
- Process kill is performed or claimed.
- Cleanup failure reports success.
- Tests, redaction scan, or closeout resilience fail.

Closeout:
- verification complete: yes
- commit: pending at artifact creation time
- push: pending at artifact creation time
- next contour: CUSTOM_CODEX_RECOVERY_PROCESS_KILL_PREFLIGHT_PASS
