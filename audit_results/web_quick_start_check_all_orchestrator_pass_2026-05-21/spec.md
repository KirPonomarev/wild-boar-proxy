# Spec: WEB_QUICK_START_CHECK_ALL_ORCHESTRATOR_PASS

## Objective

Turn Quick Start `Проверить всё` into a real sandbox-owned verify bundle that
composes already-admitted account truth, API truth, and bounded runtime readonly
truth without introducing hidden mutations or fake green states.

## In Scope

- add a server-owned `quick_start_check_all` UI action in sandbox phase only
- compose account, API, and runtime readonly contributions into one bundle
- keep the bundle verify-only and explicitly mark hidden mutations absent
- require account/API refresh proof before showing `ok_refresh_complete`
- wire the Quick Start button and ledger to the new bundle result
- cover ready and partial branches with tests
- capture direct packet evidence and browser evidence

## Out of Scope

- new CLI monolith for Check All
- account lifecycle or route lifecycle expansion in Quick Start
- API setup/create through browser
- desktop port
- redesign or runtime repair work

## Constraints

- sandbox-only execution surfaces
- no browser `token`, `secret`, `path`, `auth`, or `backend_id` input
- no fixture fallback as live truth
- no hidden mutating actions inside the bundle
- runtime readonly acts only as a bounded contribution, not a production-ready
  claim

## Assumptions

- account onboarding proof from the previous contour remains valid
- the sandbox harness can reuse an isolated root assembled from prior account
  and API evidence roots without touching the working Codex profile/data
- a verify-only route check plus sandbox-owned refresh is sufficient API truth
  for this contour

## Acceptance Criteria

- [x] Quick Start exposes `Проверить всё` from sandbox action metadata
- [x] `quick_start_check_all` uses only admitted sandbox/server-owned surfaces
- [x] the bundle records `hidden_mutation_absent=true`
- [x] account/API/runtime sub-results normalize into `ready / partial / failed / running`
- [x] Quick Start reaches `ok_refresh_complete` only after sandbox-owned account
      and API refresh
- [x] browser evidence shows a real click path and ledger entry
- [x] no fixture or stale-green fallback appears in the final verdict

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
- build:
  - `git diff --check`
- manual:
  - direct `POST /api/action {"ui_action":"quick_start_check_all"}` on the
    sandbox harness
- live evidence:
  - browser run against `http://127.0.0.1:58610/?source=live&screen=quick-start`
  - direct packet and readonly refresh captures under
    `audit_results/web_quick_start_check_all_orchestrator_pass_2026-05-21/evidence/`

## Open Questions

- no bounded mutating follow-up is needed for this contour; next work remains
  `WEB_QUICK_START_OPERATOR_SESSION_SANDBOX_PASS`
