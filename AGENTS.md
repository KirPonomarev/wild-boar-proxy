<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy Agent Bootloader

This file is the operational entrypoint for agents working in this repository.
The full workflow canon lives in [WORKFLOW_OS_V1_2.md](WORKFLOW_OS_V1_2.md).

## Canon Order

When documents conflict, follow this order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

`WORKFLOW_OS_V1_2.md` governs how work is executed.
It does not override the product/runtime canon above.

## Required Defaults

- Apply proportionality. Use the lightweight path for `XS/S` work and the full
  workflow for `M/L/XL` work.
- Use `STOP_AND_DIAGNOSE` when correctness, runtime truth, or scope integrity is
  at risk.
- Use `NOTE_AND_CONTINUE` for non-blocking cleanup, future refactors, or adjacent
  observations that do not threaten correctness.
- Do not mix `runtime`, `docs`, `UI`, and `release` work in one contour unless
  the contour explicitly requires that combination.
- Treat live-runtime work as high risk. Real-path mutations require explicit
  operator authorization, declared write surfaces, and rollback expectations.
- Follow strict JSON command surfaces as the primary truth source.
- Do not infer success from cached state, logs, narrative memory, or exit code
  alone when command packets exist.

## Current Repo Boundaries

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- Execution-core truth, lifecycle policy, fallback, recovery, and staged rollout
  rules are authoritative before UI polish.
- `UI_READINESS_SPEC.md` is a readiness/spec boundary, not permission to outrun
  execution-core repair.

## Design Gate

Before rich UI expansion or design polish, require:

`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`

Until that token is truthfully earned:

- no rich UI expansion
- no design polish contour
- no mixing UI implementation into execution-core repair

## Contour Rules

- Use the contour template at [templates/CONTOUR_TEMPLATE.md](templates/CONTOUR_TEMPLATE.md).
- Use the spec template at [templates/SPEC_TEMPLATE.md](templates/SPEC_TEMPLATE.md)
  for `M/L/XL` work and any risky `S` work.
- Use the ADR template at [templates/ADR_TEMPLATE.md](templates/ADR_TEMPLATE.md)
  for expensive-to-reverse decisions.
- Use the closeout template at [templates/CLOSEOUT_TEMPLATE.md](templates/CLOSEOUT_TEMPLATE.md)
  for completed contours.

## Stop Token

Trigger `STOP_AND_DIAGNOSE` for:

- failing tests or broken builds
- unexpected blockers
- contract mismatch
- doc/code/runtime contradiction
- live mutation with unclear rollback
- hidden assumptions affecting correctness
- cross-subsystem scope creep
- contradictory command output

Resume only after evidence is preserved, the root cause is localized, a guard is
added when needed, and verification passes.

## Closeout Rule

Work is not closed by local intuition alone.
For any completed contour, require:

- verification
- scope check
- atomic commit or logically complete commit set
- push
- final closeout note

Local-only truth is not a closed contour.
