<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Server-owned workflow identity and admission boundary

## Status

Accepted

## Date

2026-08-13

## Context

The original B14 JSON surface accepted caller-supplied slot, binding,
assignment, and provider fields and executed only a deterministic fake seam.
R63 now provides a production adapter boundary, but directly exposing its full
step identity to the browser would let stale or hostile UI state compete with
the canonical actor registry. Running a second ingress stack inside the live
server would also duplicate rate limiting and create inconsistent authorization
ordering.

## Decision

The browser submits only bounded workflow intent: actor alias, prompt, dynamic
role text, context policy, optional fork source, and repo-touching intent. The
server reloads the canonical schema-v2 registry for every run, resolves each
alias, constructs exact `WorkflowStep` identities, and passes them to the R63
registry-bound adapter. The live server's registered route ingress is the only
HTTP admission layer. Live execution receives authorization only from the
existing server-start owner-authorization fact, never from the request body.

The workflow control state owns one writer lock, bounded in-memory history,
adapter, registry loader, lease root, and server authorization flag. Public
writer status reports only whether a fencing token exists, not its value.

## Alternatives Considered

1. Continue using the B14 fake dispatch seam.
   It would render a production-looking UI over synthetic execution and leave
   the product unable to use the R63 boundary.
2. Let the browser send canonical binding/provider/revision fields.
   This creates stale-identity authority in the least trusted layer and makes
   route substitution possible before registry validation.
3. Call the standalone B14 HTTP handler from the live server.
   This would apply token, CSRF, origin, and rate limiting twice and make
   protection ordering depend on which entrypoint was used.

## Consequences

- Positive: browser authority is minimal; every run binds to fresh registry
  truth; controlled and live evidence use one execution path; ingress remains
  centralized and auditable.
- Negative: the screen cannot run until a valid persisted actor registry and
  route registry are available; workflow history is process-local rather than
  resumable across restarts.
- Follow-up work: persistent workflow resume and native-primary orchestration
  require separate admitted contours and are not implied by this decision.

## Evidence

- spec: `audit_results/R64_WEB_WORKFLOW_PRODUCTION_CONTROL_SPEC_2026-08-13.md`
- tests: R64 workflow-control, live-server, and UI regressions
- runtime packet: deterministic controlled receipts and pre-network live denial
- supporting docs: `RUNTIME_CONTRACT.md`, R63 spec/ADR/closeout, finalized
  Lazyweb Agentic Search `705500ec-b6e6-449e-aaa5-826e79e17e64`
