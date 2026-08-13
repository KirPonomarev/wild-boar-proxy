<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R63 Workflow Production Dispatch

## Objective

Replace B13's fake-only dispatch claim with a registry-bound API workflow
execution path that carries bounded visible context across sequential steps,
uses the admitted transport adapter without actor substitution, preserves
fail-fast ambiguity and repo-lease cleanup, and requires explicit live-dispatch
authorization before any provider request.

## In Scope

- enrich the sequential runner's dispatch seam with server-owned dispatch,
  turn, workflow, and bounded visible-context facts while retaining the legacy
  deterministic seam for existing controlled tests;
- make `continue` carry the prior completed context material and make `fork`
  carry material from the named completed step, not only an opaque digest;
- require positive context-delivery proof from production dispatch whenever a
  step receives prior visible context;
- redact and bound provider output before receipt persistence or reuse as
  context;
- guarantee repo-lease cleanup on validation, fork, dispatch, ambiguity,
  provider mismatch, unexpected exception, and success paths;
- resolve every production step through the canonical actor registry and
  validate exact slot, binding/revision, assignment/revision, provider, route,
  model, permission, and no-fallback identity before transport execution;
- construct an exact normalized request, prepare the context-policy transport
  session, and dispatch through `ApiTransportAdapter`;
- expose controlled and live execution modes, with live mode denied unless the
  server receives an explicit per-run authorization fact;
- add a unique `R63_WORKFLOW_PRODUCTION_DISPATCH` evidence supplement and
  focused regressions for positive and fail-closed paths.

## Out of Scope

- performing a real provider request, probing credentials, changing auth,
  installing provider tools, or closing B07/B08/B10/B11 live gates;
- wiring the web control surface, UI changes, B13G admission, or B14 work;
- native-primary automation, CLI transport multiplexing, persistent workflow
  resume, parallel repo steps, public release, or publishing;
- caller-defined routes, models, endpoints, environment, credentials,
  permissions, or fallback.

## Constraints

- exact base is merged remote main
  `60e0b5cf85886c2c427403ac32cb9230389f4471`;
- a workflow step may request context policy and dynamic role text, but neither
  grants permission or overrides registry identity;
- visible context and output are redacted, length-bounded, digest-bound, and
  never emitted as raw diagnostic context;
- an ambiguous dispatch stops the run and cannot be retried, replaced, or
  routed to another actor;
- live mode requires an exact boolean authorization on the bounded run call;
  controlled mode is labeled synthetic and cannot close a live gate;
- one run holds at most one repo lease, and every owned lease is released even
  when a dispatch callback raises unexpectedly.

## Acceptance Criteria

- [ ] registry drift or caller identity drift fails before transport dispatch;
- [ ] a controlled registry-bound API workflow executes through the real
      adapter boundary and remains explicitly non-live;
- [ ] live mode is denied before credential probing or network without exact
      per-run authorization;
- [ ] an authorized live-mode test double receives `controlled=False`, exact
      identities, session, idempotency, role instruction, and visible context;
- [ ] `continue` and `fork` deliver bounded prior material and receipts prove
      its digest/source without exposing raw context;
- [ ] missing context-delivery proof, provider mismatch, ambiguity, dispatch
      error, and unexpected exceptions stop before later steps;
- [ ] repo lease is released on every terminal path;
- [ ] the R63 evidence supplement is required exactly once;
- [ ] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
      resilience gates pass on the final candidate.

## Verification

- tests: sequential-runner and registry-bound workflow API regressions;
  evidence-bundle and final-assurance regressions; repository core,
  custom-stability, and full suites;
- build: `make check`;
- manual: exact identity/request/context boundary review, no provider or auth
  side effects, scoped/full evidence truth;
- live evidence: not performed; existing live gates remain pending.

## Open Questions

- none blocking for the R63 code repair; web wiring and transport multiplexing
  remain outside this contour.
