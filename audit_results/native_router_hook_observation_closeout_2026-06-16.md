<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native Router Hook Observation Closeout

## Goal

Add a strict observation packet that proves whether a normal Codex prompt path
has explicit WBP-owned router hook evidence for `DIP` / `Agent 2`, while keeping
the lower `delegate_to_dip`, controlled-dispatch, live-smoke, UI, provider, and
Codex patch layers unchanged.

## Result

- status: completed
- final verdict: `wbp_native_router_hook_observation` now requires explicit hook evidence plus prompt-bound `delegate_to_dip` tool-call evidence and a matching delegate packet; no-hook and hook-logging-only cases fail closed
- closure state: CLOSED

## Contour Capsule

- goal: prove strict native router hook observation without claiming product-ready native free-chat routing
- branch: codex/stabilize-runtime-core
- head: 388d90bc3055ae74e6e215b244988a29a81a309b pre-closeout base; closure commit includes this evidence and scoped MCP/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/native_router_hook_observation_closeout_2026-06-16.md
- tests run: MCP delegate unittest and pytest passed; Python compile passed; diff whitespace and line-length checks passed; router-hook repro probes passed; `make test-core` passed; independent audit and re-check passed; closeout resilience check passed
- blocked risks: no-hook false green; hook-logging-only false green; text imitation as DIP; Codex sub-agent substitution as DIP; prompt/tool/delegate digest mismatch; browser-supplied route/backend/secret/model authority; raw route id leakage; product-ready or native-free-chat claims from observation packets
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_mcp_delegate` -> 57 tests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" python3 -m pytest -q tests/test_mcp_delegate.py` -> 57 passed, 24 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- build: `git diff --check` -> passed
- build: line-length scan for `wild_boar_proxy/mcp_delegate.py` and `tests/test_mcp_delegate.py` -> passed
- manual: no-hook repro returned `error`, `blocked`, `router_hook_observed=false`, and hook-missing blocking reasons
- manual: full hook repro returned `ok`, `observed`, `router_hook_observed=true`, while keeping `product_ready=false` and `native_free_chat_router_proven=false`
- manual: independent auditor Linnaeus found a no-hook false-green bug; the gate was changed to require `hook_observed_prompt`, `hook_can_enforce_router`, and `hook_can_route_delegate_to_dip`; auditor re-check passed
- live verification: no external provider network call was executed in this contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_native_router_hook_observation`
- report: success packets prove `router_hook_observed=true`, `wbp_owned_surface_called=true`, `prompt_digest_bound=true`, `tool_call_digest_bound=true`, `alias_context_read=true`, `local_codex_subagent_used_as_dip=false`, `browser_can_supply_route_authority=false`, `browser_can_supply_model_authority=false`, `secret_value_exposed=false`, `raw_backend_details_exposed=false`, `product_ready=false`, and `native_free_chat_router_proven=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped MCP/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, raw prompts, raw transcripts, raw provider responses, route secrets, backend URLs, provider headers, API keys, and raw route ids were not recorded

## Notes

- blockers encountered: independent audit found that prompt-bound MCP tool-call evidence alone could green the first hook packet; explicit hook evidence is now required
- residual risk: this contour proves packet shape and strict evidence gating with synthetic transcript evidence; it does not prove completed native free-chat product integration
- resume from here: CLOSED
