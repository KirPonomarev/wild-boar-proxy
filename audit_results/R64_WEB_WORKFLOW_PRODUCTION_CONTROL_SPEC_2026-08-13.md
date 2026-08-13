<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R64 Web Workflow Production Control

## Objective

Wire the R63 registry-bound workflow execution boundary into the actual local
web server and ship an operator workflow screen that can compose, run, inspect,
and recover bounded multi-actor workflows without granting the browser route,
provider, credential, binding, assignment, or authorization authority.

## In Scope

- replace the B14 fake-only workflow run path with R63 registry-bound controlled
  and authorization-gated live execution;
- resolve browser-supplied aliases to exact server-owned registry identities on
  every run and reject identity-like browser fields;
- register workflow gate, status, history, and run routes in the canonical web
  route/effect table and reuse the live server's loopback, Host, Origin, token,
  CSRF, content-type, body-size, and rate-limit ingress;
- keep one server-owned writer lock and bounded in-memory workflow history with
  sanitized receipts and explicit controlled/live evidence facts;
- build a first-class workflow screen using the existing Iosevka, warm-neutral,
  blue-accent token system and the finalized Lazyweb evidence set;
- expose persistent API actor slots, ordered step configuration, context-policy
  transitions, execution readiness, progress/receipts, and failure history with
  accessible keyboard and responsive behavior;
- add focused control-boundary, live-server integration, UI contract, and
  JavaScript behavior regressions plus the R64 spec, ADR, and closeout.

## Out of Scope

- a real provider request, credential installation, credential mutation, or
  closure of the pending B07/B08/B10/B11 live gates;
- native-primary/ChatGPT workflow execution, parallel steps, persistent resume,
  ACP, arbitrary browser-defined routes/models/providers, or repo-tool grants;
- changes to the canonical actor registry schema, command/state schemas, or
  public release and publication.

## Constraints

- exact contour base is merged `origin/main`
  `43fa86c5b1cf15a2d9a172389f99056bea931274`;
- the design gate is independently earned with marker
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` and packet digest
  `be4ff1c2776b29b78042ef5754d854c774a5efd1b8c17ecd65f20b28bbf1d632`;
- Lazyweb Agentic Search
  `705500ec-b6e6-449e-aaa5-826e79e17e64` supplies the evidence boundary:
  persistent actor slots, linear progress, split configuration/results,
  operational failure history, and visible guardrails;
- browser step input is limited to alias, bounded prompt, bounded role text,
  context policy, fork source, and repo-touching intent; canonical identity and
  transport facts remain server-owned;
- live mode is denied before credential probing or network unless the server
  process has the existing exact owner-authorization fact; no live call is made
  during this contour;
- no fallback, actor substitution, secret value, raw backend detail, path, or
  fencing token may be exposed to the browser;
- workflow POST is an `EFFECT_MUTATE` route because it can execute provider
  work, even when a controlled test double is used.

## Assumptions

- the canonical schema-v2 actor registry shares the persisted agent-bindings
  path under the owner-managed runtime directory;
- the external-model route registry lives under the owner-managed
  `external-models` root already used by the live server;
- R63 remains the single authority for sequential ordering, visible-context
  delivery proof, ambiguity handling, and repo-lease cleanup.

## Acceptance Criteria

- [x] all four workflow routes are present in the canonical route registry and
      every registered route has a bound handler;
- [x] controlled workflow runs cross the real registry and adapter boundary and
      return exact per-step receipts without a provider network call;
- [x] live workflow requests are rejected before credentials/network when the
      server authorization fact is absent;
- [x] browser identity/route/provider/model/revision fields are rejected and
      aliases are resolved from fresh canonical registry truth on each run;
- [x] writer status is single-writer, browser-safe, and history is bounded with
      success/failure/receipt facts;
- [x] the workflow UI exposes persistent slots, ordered steps, context policy,
      readiness, progress, receipts, and history without accepting secrets;
- [x] keyboard submission, visible focus, labeled fields, inline errors,
      aria-live status, reduced motion, and responsive layout are covered;
- [x] focused, integration, UI, and complete repository-suite verification are
      exercised locally; final post-fix truth is adjudicated by exact-SHA
      protected CI before merge.

## Verification

- tests: workflow-control unit tests, workflow API dispatch tests, live-server
  workflow route tests, UI markup/JavaScript behavior tests, then repository
  core/custom/web/full suites;
- build: `make check` and JavaScript syntax/runtime checks;
- manual: browser-level visual and keyboard inspection of the local screen,
  registry/adapter identity review, secret/redaction review, and diff hygiene;
- live evidence: no external provider request; live denial and authorized test
  doubles only.

## Open Questions

- None blocking.
