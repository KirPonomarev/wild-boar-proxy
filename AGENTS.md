<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy Agent Bootloader

This file is the operational entrypoint for agents working in this repository.
The full workflow canon lives in [WORKFLOW_OS_V1_2.md](WORKFLOW_OS_V1_2.md).

## Canon Order

When documents conflict, follow this order:

1. `CANON.md`
2. `RUNTIME_CONTRACT.md`
3. `STATE_SCHEMA.md`
4. `COMMAND_API.md`
5. `DELIVERY_RULES.md`
6. `README.md`

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
- Do not create or rely on repo-resident master plans, roadmaps, next-contour
  queues, or repair plans. Active planning belongs outside the repo; this repo
  keeps canon, contracts, implementation, tests, and completed evidence.
- Treat `audit_results/` as historical evidence only. It is not an active
  navigation source for "what is next"; use the current task thread and the
  current contour's completed closeout only.

## Current Repo Boundaries

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- Execution-core truth, lifecycle policy, fallback, recovery, and staged rollout
  rules are authoritative before UI polish.
- `UI_READINESS_SPEC.md` is a readiness/spec boundary, not permission to outrun
  execution-core repair.

## Custom Codex Agent Aliases

When running inside a Wild Boar Proxy Custom Codex profile and `WBP_PROFILE_DIR`
is present, requests that address `Codex`, `DIP`, `Agent 1`, or `Agent 2` must
first read:

`$WBP_PROFILE_DIR/wbp-agent-runtime-context.json`

Treat that file as the server-issued runtime truth for alias-to-slot binding and
API route selection. Do not infer route ids from tests, docs, audit history,
chat history, or old examples. If the context file is missing, answer
`FAIL_ALIAS_CONTEXT_MISSING`.

If `deepseek_live_format_check_bridge` is present and enabled, use that local
WBP bridge before direct external network calls. Try `url_candidates` in order,
bypassing proxies for local bridge calls. The bridge URL is loopback-only and
server-owned; do not add secrets, backend fields, or route ids that are not
listed in `allowed_api_route_ids`. If all bridge candidates fail, use
`deepseek_live_format_check_file_bridge` when present before any direct provider
network call. This file bridge is server-owned and exists for Custom Codex
sandboxes that cannot open sockets (`PermissionError` / `Operation not
permitted`) even to loopback. Prefer the file bridge `shell_command_template`
when present, replacing only `<expected_text>`. Do not collapse the template into
inline shell variable assignments before `printf`; keep statement separators or
newlines so `request_file` and `response_file` are real shell variables. If no
template exists, write only the documented request JSON into `request_dir`, poll
the matching response JSON from `response_dir`, and require the response
`output_text` to match the expected text exactly. If the file bridge is
unavailable, use `deepseek_live_format_check_cli_command` when present instead of
ambient `python3`. If the bridge/API lane still fails, report the actual
`machine_error_code`, HTTP error, or per-candidate transport error and do not
imitate the second agent locally.

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
- Contour/spec/closeout artifacts may document admitted scope and completed
  evidence. They must not become a forward roadmap or master plan.

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
- `python3 tools/check_closeout_resilience.py` for any new or changed
  `audit_results/*closeout*.md`
- scope check
- atomic commit or logically complete commit set
- push
- final closeout note

Local-only truth is not a closed contour.

## Forget-Proof Enforcement

Closeout resilience is enforced both by policy and by git hooks.

- One-time setup per clone/session:
  `bash tools/install_git_hooks.sh`
- Commit-time gate:
  `.githooks/pre-commit` runs
  `python3 tools/check_closeout_resilience.py --staged-only`
- Any commit with a changed `audit_results/*closeout*.md` and missing/placeholder
  `Contour Capsule` or `resume from here` fields must fail.
- Any new or changed closeout that stores next-contour pointers, master-plan
  routes, or future execution queues must fail. Completed evidence closes a
  contour; it must not seed the next one.
