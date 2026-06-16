<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Router Hook Source Admission Closeout

## Goal

Add a strict source-admission packet for WBP-owned router hook evidence, then
wire `wbp_native_router_hook_observation` so it cannot turn green from a
manual or synthetic `hook_packet`.

## Result

- status: completed
- final verdict: `wbp_router_hook_source_admission` now admits only WBP-owned,
  prompt-bound, run-bound, probe/read-only source evidence; native router hook
  observation now requires that admitted source packet and blocks legacy/manual
  hook dictionaries
- closure state: CLOSED

## Contour Capsule

- goal: close the false-green gap where three truthy hook booleans could stand
  in for real WBP-owned router hook source evidence
- branch: codex/stabilize-runtime-core
- head: 9d123de063dc6b3651d62384e12c5a3f5da3a046 pre-closeout base; closure
  commit includes this evidence and scoped MCP/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py;
  audit_results/router_hook_source_admission_closeout_2026-06-16.md
- tests run: Python compile passed; MCP delegate unittest and pytest passed;
  diff whitespace check passed; adversarial packet smoke passed; `make
  test-core` passed; independent read-only audit passed; closeout resilience
  check passed
- blocked risks: manual hook packet false green; synthetic hook packet false
  green; prompt/browser supplied hook authority; source prompt/run digest drift;
  source write side effects; raw prompt, raw route id, backend detail, or secret
  exposure; product-ready or native-free-chat claims from source/observation
  packets
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- tests: `python3 -m unittest tests.test_mcp_delegate` -> 62 tests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"
  python3 -m pytest -q tests/test_mcp_delegate.py` -> 62 passed, 32 subtests
  passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- manual: adversarial packet smoke returned `manual_status=error`,
  `manual_observed=false`, `admitted_status=ok`, `admitted_observed=true`,
  `admitted_product_ready=false`, and
  `admitted_native_free_chat_router_proven=false`
- manual: independent auditor Aristotle confirmed that manual `hook_packet`
  no longer bypasses source admission, source admission blocks the listed
  false-green classes, and no UI/live-provider/Codex-patch/runtime-write layer
  was added
- live verification: no external provider network call was executed in this
  contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_router_hook_source_admission`
- packet: `wbp_native_router_hook_observation`
- report: success packets prove `source_status=ok`, `source_wbp_owned=true`,
  `source_effect=probe`, `source_run_digest_present=true`,
  `source_prompt_digest_bound=true`, `hook_observed_prompt=true`,
  `hook_can_enforce_router=true`, `hook_can_route_delegate_to_dip=true`,
  `manual_hook_packet_used=false`, `prompt_supplied_hook_flags=false`,
  `browser_supplied_hook_flags=false`, `product_ready=false`, and
  `native_free_chat_router_proven=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped MCP/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged
  and untouched
- private-data risk reviewed: auth files, raw prompts, raw transcripts, raw
  provider responses, route ids, backend URLs, provider headers, API keys, and
  secret values were not recorded

## Notes

- blockers encountered: the prior observation consumer accepted arbitrary hook
  booleans; it now requires an admitted source packet
- residual risk: this contour proves source-admission and observation gating at
  packet level; it does not claim completed native free-chat product routing
- resume from here: CLOSED
