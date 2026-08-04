<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B15_OPTIONAL Persistent ACP Admission

## Objective

Perform the physical protocol admission for the optional persistent ACP
(Agent Client Protocol) surface. If the protocol is unavailable or
unstable, close as `OPTIONAL_DEFERRED_ACP` with evidence. B15 code is
independent of pending live credentials and does not substitute for
one-shot acceptance.

## In Scope

- `wild_boar_proxy/optional_acp_admission.py` (new):
  - availability probe: ACP server/client binary candidates and
    repository implementation presence (transport kind only, no runtime)
  - admission evaluation packet: physical protocol admission result with
    per-criterion evidence; unavailable or unstable -> terminal
    `OPTIONAL_DEFERRED_ACP`
- tests: `tests/test_optional_acp_admission.py`
- B15_OPTIONAL spec + closeout in `audit_results/`

## Out of Scope

- ACP implementation (only when physically admitted)
- live credential phases
- any canon change (no command/state schema touch)

## Constraints

- admission is never assumed: no ACP server, no stable implementation ->
  deferred with evidence
- the probe makes no network calls and touches no credential stores
- deferred is a valid terminal result

## Assumptions

- the repository carries only the `cli_acp` transport-kind enum today,
  with no ACP server or client implementation

## Acceptance Criteria

- [ ] probe reports facts (binary candidates, repo implementation
      presence)
- [ ] unavailable or unstable ACP -> `OPTIONAL_DEFERRED_ACP` terminal
      with evidence
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_optional_acp_admission.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none

## Open Questions

- None blocking.
