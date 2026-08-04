<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B14 Web Workflow Control Surface

## Objective

After B13G, implement the web management control surface for the
execution core: workflow run controls (B13 integration), workflow history,
writer status, capability/evidence badges, provider/transport/model
selection facts, aliases, credential presence, assignments, and context
policies — protected by token, rate limit, origin/CSRF checks, strict
packets, loopback policy, and secret redaction. The dispatch seam is
controlled-only in B14; live dispatch is rejected with a typed error.

## In Scope

- `wild_boar_proxy/web_workflow_control.py` (new):
  - `WorkflowRunHistory`: bounded, thread-safe run history
  - `WorkflowControlState`: writer lock (single writer with fencing
    token), gate facts, capability badges, provider/transport/model
    selection facts, alias bindings, credential presence, assignments,
    context policies
  - `handle_workflow_control_request(...)`: strict request handler with
    loopback-only client check, token verification, rate limiting,
    origin allow-check, CSRF verification for POST, and strict packets
    (all responses via `build_command_payload` with redaction)
  - endpoints:
    - GET `/api/workflow/gate` — design-gate badge
    - GET `/api/workflow/history` — workflow run history
    - GET `/api/workflow/status` — writer status + badges + selection
      facts + credential presence + assignments + context policies
    - POST `/api/workflow/run` — run a sequential workflow (B13 runner)
      in controlled dispatch mode; live dispatch rejected
      (`WORKFLOW_LIVE_DISPATCH_NOT_IMPLEMENTED`)
  - dispatch mode is `controlled_fake` only; `live` is rejected
- tests: `tests/test_web_workflow_control.py`
- B14 spec + closeout in `audit_results/`

## Out of Scope

- live provider dispatch from the web surface (live phases)
- UI page rendering (this surface is JSON control endpoints)
- persistent ACP (B15)
- any canon change (no command/state schema touch)

## Constraints

- POST endpoints require a valid web token and CSRF; origin checks apply;
  rate limits apply; clients are loopback-only
- all responses are strict command packets (semantics-inspected in tests)
- secret values are redacted by the packet contract; never echoed
- the writer lock allows one workflow writer at a time (fencing token)
- live dispatch is never simulated: it is rejected with a typed error
- workflow history is bounded

## Assumptions

- the existing web token / rate-limit / origin / CSRF machinery is reused;
- B13 runner executes with the controlled dispatch seam in B14

## Acceptance Criteria

- [ ] gate/history/status endpoints return strict packets
- [ ] POST run requires token, CSRF, origin, rate limit, loopback client
- [ ] workflow runs appear in history with independent receipts
- [ ] writer status is single-writer with fencing token
- [ ] live dispatch mode is rejected with a typed error
- [ ] secret values never appear in any response
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_web_workflow_control.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (controlled dispatch only)

## Open Questions

- None blocking.
