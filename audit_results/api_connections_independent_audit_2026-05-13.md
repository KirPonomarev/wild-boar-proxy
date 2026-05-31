<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Connections Admission Independent Audit

Contour ID: `API_CONNECTIONS_ADMISSION_AND_CANON_ALIGNMENT`
Date: 2026-05-13
Auditor: independent canon/layering explorer
Verdict: `PASS_WITH_GUARDS`

## Audit Scope

The audit checked whether admitting `API-подключения` as a future product screen
conflicts with the canon, design gate, runtime truth rules, or engine/control
boundary.

No files were changed by the auditor.

## Findings

### 1. Engine/control boundary supports spec-only admission

`Wild Boar Proxy` is the managing/control layer, while `CLIProxyAPI` remains the
engine. This supports a product-facing `API-подключения` admission only if the
feature remains a control-layer wrapper over strict command surfaces.

Evidence:

- `CANON.md:24-32`
- `MASTER_PLAN.md:223-259`

Guard:

- Do not implement low-level provider execution, transport, routing, auth flow,
  or continuous token routing in UI.

### 2. Strict JSON remains mandatory

UI and automation must use strict JSON command packets and must not parse plain
text or logs.

Evidence:

- `COMMAND_API.md:10-14`
- `MASTER_PLAN.md:374-417`
- `AGENTS.md:36`

Guard:

- Future `API-подключения` UI must use command packets only.
- No direct `routes.json`, `state.json`, or `secrets.env` truth reads are
  admitted for product UI.

### 3. Design gate is not violated by this contour

The design gate blocks rich UI expansion and design polish before
`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`. This contour is
admission/spec-only and does not implement UI behavior or visual polish.

Evidence:

- `AGENTS.md:49-59`
- `MASTER_PLAN.md:275-280`

Guard:

- Do not add sidebar items, screens, CSS, or UI behavior in this contour.

### 4. The high-risk semantic point is active routing

A future `Вкл` button can easily overclaim. If the command only changes
`enabled`, the product label must be `Разрешить маршрут`, not `Сделать
активным`.

Evidence:

- `MASTER_PLAN.md:225-227`
- `COMMAND_API.md:439`
- `COMMAND_API.md:765-821`

Guard:

- `active`, `primary`, and failover language require explicit owner truth.

### 5. Failover must remain separate

Automatic failover touches provider execution and routing semantics. It cannot
be smuggled into a UI admission contour.

Evidence:

- `CANON.md:31-32`
- `MASTER_PLAN.md:261-279`
- `RUNTIME_CONTRACT.md:84-125`

Guard:

- Keep failover as `API_CONNECTIONS_FAILOVER_POLICY_DECISION` before any
  implementation.

## Required Stop Conditions For Future Work

- Tests fail or command output contradicts docs.
- Browser would send tokens, raw route config, shell, argv, or arbitrary paths.
- UI copy implies active traffic without command proof.
- UI treats route validation as runtime readiness.
- UI reads route/state/secret files directly as truth.
- Failover requires duplicating engine-layer routing inside UI.

## Audit Conclusion

The contour is canon-compatible as admission/spec work. It would become
canon-unsafe if it mutates runtime, implements UI, exposes token input, claims
active routing from `enabled=true`, or presents `fallback_eligible` as
automatic failover.
