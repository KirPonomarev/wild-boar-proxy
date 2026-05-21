# Spec: DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS

## Objective

Port the already-proven web Quick Start continuity flow onto the admitted Tk
desktop shell without widening semantics, inputs, or truth sources.

## In Scope

- wire desktop Quick Start summary to the same account truth surface
- wire desktop Quick Start API summary to the same external-models truth surface
- wire desktop `Check All` to the same bounded verify bundle semantics
- carry action ledger parity into the desktop shell
- prove one desktop continuity scenario on a sandbox-owned harness

## Out of Scope

- from-empty rebuild
- packaging or distribution work
- redesign or desktop polish
- new desktop-only commands
- lifecycle expansion beyond already admitted sandbox actions

## Constraints

- sandbox only
- no raw `token`, `secret`, `path`, `auth`, or `backend_id` input in desktop UI
- success only by packet + refresh proof
- desktop shell state is not a truth source
- use admitted Tk shell path from `DESKTOP_EXECUTABLE_BRIDGE_ADMISSION_PASS`

## Assumptions

- the admitted Tk shell remains operational on the bundled runtime
- external-models synthetic adapter may be started inside the sandbox harness so
  desktop continuity can observe the same bounded secret/token readiness used by
  the proven web API lane
- direct worker-path automation is acceptable for desktop smoke evidence because
  public dispatch/confirmation wiring is covered by unit tests and the smoke is
  only proving real packet + refresh flow through the desktop layer

## Acceptance Criteria

- [x] desktop Quick Start renders account truth from real command snapshots
- [x] desktop Quick Start renders API truth from real external-models snapshots
- [x] desktop `Check All` reaches `ready` only from bounded packet + refresh proof
- [x] action ledger records desktop API check and desktop check-all actions
- [x] desktop continuity smoke stays within sandbox and avoids forbidden inputs

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - bundled-runtime Tk shell instantiated on a sandbox harness and drove
    refresh -> API check -> check-all -> ledger capture
- live evidence:
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/evidence/desktop_continuity_smoke.json`

## Open Questions

- none within the contour boundary once the admitted Tk shell is treated as the
  baseline desktop surface
