# Spec: WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS

## Objective

Close the current repo-truth contour for bounded server-owned API route create or
adopt in the web UI without widening admission into a generic route builder.
This is a re-entry closure-pass over the already implemented `api_route_connect`
lane, plus a focused regression test for the `adopted_existing_route` branch.

## In Scope

- Reconfirm that `api_route_connect` is the only admitted create/adopt lane.
- Reconfirm that the browser payload stays bounded to `ui_action` only.
- Reconfirm that owner credential status/admit, server-owned route spec,
  add/adopt, validate, and readonly refresh remain the exact truth chain.
- Add focused regression coverage for the existing-route adopt branch.
- Produce fresh closeout artifacts under the current contour name.

## Out of Scope

- Generic route builder, route draft, or route update UI.
- Browser secret/token/api_key/path/provider config intake.
- Provider OAuth/login automation.
- Non-sandbox live runtime mutation.
- Broad API surface redesign or unrelated runtime work.

## Constraints

- Canon order: `CANON.md`, `MASTER_PLAN.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- `api_route_connect` must remain server-owned and sandbox-bounded.
- Success requires machine-backed action/result truth and readonly refresh truth.
- Browser must not influence route id, route spec, secret, path, or auth object.

## Assumptions

- Existing implementation entered the branch in commit
  `607ceb10bd31264e06557bdcfb0b870fb6d0b2a2`.
- Existing browser proof under
  `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/` remains a
  valid factual artifact for the create path.
- The current gap is proof/coverage closure, not missing server-owned lane
  implementation.

## Acceptance Criteria

- [x] `api_route_connect` remains the only admitted bounded create/adopt web lane.
- [x] Generic route builder surfaces remain not admitted.
- [x] Browser payload for route connect remains bounded and rejects forbidden fields.
- [x] Existing-route adopt branch has direct regression coverage.
- [x] Focused tests pass.
- [x] Fresh closeout artifacts exist under the current contour name.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - focused unittest gate for `api_route_connect` create/adopt/credential/UI paths
- build:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - inspect existing server-owned lane in `web_design_live_server.py`
  - inspect prior factual browser artifacts from
    `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/`
- live evidence:
  - reused browser evidence from
    `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/evidence/`

## Open Questions

- A dedicated provider-specific owner-source/login contour is still needed for
  real external-provider onboarding beyond server-owned sandbox route admission.
