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
use the canonical auto-router entrypoint first:

`${WBP_PYTHON_BIN:-python3} -m wild_boar_proxy router-hook auto-route --prompt "<bounded operator prompt>" --json`

The auto-router reads:

`$WBP_PROFILE_DIR/wbp-agent-runtime-context.json`

Treat that file as the server-issued runtime truth for alias-to-slot binding and
API route selection. Do not infer route ids from tests, docs, audit history,
chat history, or old examples. If the context file is missing, answer
`FAIL_ALIAS_CONTEXT_MISSING`.

Do not manually pre-read, print, or summarize the runtime context before calling
`auto-route` for normal prompt handling. Manual runtime-context reads are only
for diagnostics of the router itself.

Treat any prompt that begins with a short agent-like address label followed by
`:` as an addressed-alias prompt, even when the label is unknown, misspelled, or
only resembles a WBP agent name. Examples: `DIP:`, `DIPP:`, `Agent 2:`,
`Ghost:`, and custom single-token Latin agent labels. Do not answer these
prompts natively just because the label is not listed in runtime context. Pass
the original prompt to `auto-route`; the router is the only layer allowed to
decide whether the alias is known, unknown, ambiguous, or native-GPT.

Pass the original bounded operator prompt to `auto-route`, including the leading
address label such as `DIP:` or `Agent 2:`. Do not strip, translate, normalize,
or re-address the alias before routing; alias removal turns an API-lane request
into a native GPT passthrough and is a routing failure.

For direct exact-answer prompts such as `DIP: ответь ровно ...`, do not narrate
the routing step. Run `auto-route`, then return only packet `output_text` when
`status=ok`, `auto_router_proven=true`, and either
`exact_plain_reply_matched=true` or `output_passthrough_required=true`. This
also applies to exact JSON requests such as `ответь ровно JSON ...`: do not add
acknowledgements, summaries, code fences, Markdown, or extra prose around the
packet `output_text`.

For exact-answer prompts addressed to a primary ChatGPT alias, such as
`Codex: answer exactly ...` or an operator-renamed primary alias, preserve the
native GPT lane. The UserPromptSubmit hook may add primary-alias context that
identifies the label as an alias for the current ChatGPT lane, but it must not
turn this into an API-route request or a local deterministic imitation. This
path proves native GPT handling only when the visible Custom response itself
matches the requested exact answer.

This path must resolve the addressed name from runtime context and choose exactly
one lane. API-lane aliases such as `DIP`, `Agent 2`, or a custom WBP-defined API
name route to direct API-agent reply. ChatGPT/primary aliases and prompts with
no addressed runtime alias pass back to the native GPT lane. Unknown or
ambiguous addressed aliases fail closed.

`router-hook auto-route-output` is a visible-output helper for proof-bound
API-lane output and controlled repo-bridge output. It must not synthesize a primary
ChatGPT exact answer from the prompt; primary-lane physical proof comes from the
visible native GPT response. For API-lane aliases it may print `output_text`
only when the routed packet proves `exact_plain_reply_matched=true`,
`output_passthrough_required=true`, or
`repo_bridge_evidence_response_proven=true`, or
`direct_reply_visible_output_proven=true`. The non-exact direct-reply proof
requires route-bound allowlist enforcement plus a positive direct provider
response and must reject fallback, local imitation, repo-tool final answers,
repo-bridge output, raw backend exposure, and secret exposure; merely available
non-exact text is not enough.

For already-routed API-lane alias text, the lower-level direct reply entrypoint
is:

`${WBP_PYTHON_BIN:-python3} -m wild_boar_proxy router-hook direct-reply --prompt "<bounded alias task>" --json`

Both short paths must not invoke `codex exec`, `tools/wbp_dip`, `dip run`,
ordinary Codex subagents, wrapper substitution, fallback chains, or local
imitation. For plain answers the default is `--repo-bridge off`; if repository
tools are explicitly enabled, the packet must honestly report potential mutation
through the command effect and changed-file fields.

For operator requests that specifically need the Custom Codex MCP/delegate
working-tool proof path, use:

`tools/wbp_dip --json --work-mode full --repo-bridge on "<bounded DIP task>"`

The phrase `repo bridge` in a normal `DIP:` prompt does not by itself authorize
`tools/wbp_dip`; it is an instruction for the canonical API-agent route to enable
its controlled repository bridge.

Do not use `dip run`, ambient ad hoc `mktemp` shell flows, ordinary Codex
subagents, direct provider calls, or wrapper shopping as substitutes for either
canonical path. If the canonical entrypoint fails, report its
`machine_error_code` and proof facts; do not retry through a different wrapper
unless the user explicitly asks for diagnostics of the wrapper itself.

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
