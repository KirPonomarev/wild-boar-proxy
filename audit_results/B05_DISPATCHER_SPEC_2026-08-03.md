<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B05 Dispatcher, Assignments, Permissions, Diagnostics

## Objective

Implement the generic fail-closed actor dispatcher: alias/binding/assignment/
context resolution, permission intersection, one repo lease, strict typed
errors, dispatch diagnostics, and no fallback/imitation. Update the affected
command contract (`COMMAND_API.md`) in the same contour.

## In Scope

- `wild_boar_proxy/actor_dispatcher.py`: canonical registry resolution
  (alias -> slot binding -> actor -> role assignment), legacy v1 bindings as
  an explicitly reported wire-compatible fallback, permission intersection
  (binding ceiling / operator grant / adapter capability / runtime policy),
  context-policy enforcement (`continue`/`fresh`/`fork` with digest
  requirement), strict fail-closed errors, normalized dispatch request
  builder, `no_fallback`/`cross_provider_fallback=false` plan truth
- `wild_boar_proxy/repo_lease.py`: exclusive repository lease (flock,
  fencing token, holder metadata, stale recovery) — one repo-touching
  operation at a time
- `dispatch resolve <alias> --json` read surface + `COMMAND_API.md` section
- tests: `tests/test_actor_dispatcher.py`
- B05 spec + closeout in `audit_results/`

## Out of Scope

- actual provider dispatch and adapters (B07/B08)
- workflow runner (B13)
- web UI (B14)
- ledger capture wiring (B04 module exists; hook wiring pending physical
  spike)
- any engine runtime truth change

## Constraints

- assignment and role can only request or reduce permission; they never grant
- unknown/ambiguous aliases fail closed; no wrapper shopping, no local
  imitation, no fallback chains
- ambiguous delivery is never retried
- repo-touching operations are serialized via the exclusive lease
- `dispatch resolve` is read-only: `changed_files=[]`, no runtime writes
- strict JSON packets pass `inspect_command_packet_semantics`

## Assumptions

- The canonical actor registry (B02) is the primary resolution source;
  legacy v1 bindings remain wire-compatible until B06 regression closure

## Acceptance Criteria

- [ ] canonical and legacy resolution produce bounded dispatch plans
- [ ] permission intersection is conservative; grants cannot escalate
- [ ] stale routes, unknown aliases, drift, and permission denial fail closed
- [ ] fork policy requires an exact context digest
- [ ] repo lease: one holder, fencing-token release, stale recovery
- [ ] `dispatch resolve <alias> --json` emits strict packets
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_actor_dispatcher.py`; `make check`; `make test-core`;
  `make test-custom-stability`; `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: CLI smoke (`dispatch resolve` no-state, canonical, unknown alias)
- live evidence: none

## Open Questions

- None blocking.
