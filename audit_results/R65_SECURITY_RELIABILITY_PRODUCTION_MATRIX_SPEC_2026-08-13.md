<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R65 Security / Reliability Production-Path Matrix

## Objective

Re-prove B17 against the production paths admitted by R59-R64. Replace weak
helper-only claims with deterministic checks of registry-bound workflow
dispatch, identity/revision drift rejection, provider-route failure handling,
web ingress controls, writer fencing, restart behavior, redaction, and
unauthorized-live fail-stop behavior.

## In Scope

- strengthen `wild_boar_proxy/security_reliability_matrix.py` without network
  or credential access;
- exercise the real actor registry, API transport adapter, sequential workflow
  dispatcher, repository lease, and web workflow control boundary;
- add explicit production-workflow and web-control matrix entries;
- keep Codex-protected surfaces guarded and unread;
- update focused tests and produce one resilient closeout.

## Out of Scope

- live provider dispatch or credential reads;
- public release, rollout, or protected-network mutation;
- UI design or product feature expansion;
- changes to canon or public command/state schemas.

## Acceptance Criteria

- stale binding revision is rejected before adapter dispatch;
- disabled provider route fails before provider dispatch and never falls back;
- controlled two-step production workflow proves independent receipts,
  visible context delivery, and lease cleanup;
- unauthorized live workflow stops before credential probe or network dispatch;
- loopback, token, origin, CSRF, rate-limit, writer fencing, browser-authority,
  and secret-redaction boundaries are exercised;
- restart probe recovers durable registry/ledger truth while process history is
  honestly reset;
- aggregate matrix remains strict, secret-free, and contains no failed checks;
- focused, affected, repository, and required CI gates pass before merge.

## Verification

- `tests/test_security_reliability_matrix.py`;
- affected workflow/web/transport test modules;
- `make check`, `make test-core`, `make test-custom-stability`,
  `make test-web-e2e`, and one `make test-full` for the material contour;
- exact-candidate GitHub CI and remote-main readback.

## Safety

- all dispatch is `controlled`; no provider network is authorized;
- no credential value or primary Codex surface is read;
- temporary probe roots are isolated under `/tmp`;
- no public release action is authorized.
