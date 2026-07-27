<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Router Hook Source Event Producer Closeout

## Goal

Create a capability-grounded WBP-owned producer for router hook source evidence
and make source admission reject manually shaped source events.

## Result

- status: completed
- final verdict: `wbp_router_hook_source_event` now derives router-hook source
  claims from prompt-bound Codex exec evidence plus explicit WBP-owned control
  boundary evidence; `wbp_router_hook_source_admission` now requires the
  producer packet shape, produced status, producer marker, and matching claim
  digest
- closure state: CLOSED

## Contour Capsule

- goal: remove the synthetic source-event false green where an arbitrary mapping
  could claim `hook_can_enforce_router=true`
- branch: codex/stabilize-runtime-core
- head: e35ffd2dcd97e11a8a4be49dff727aa204fd2c35 pre-closeout base; closure
  commit includes this evidence and scoped MCP/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py;
  audit_results/router_hook_source_event_producer_closeout_2026-06-16.md
- tests run: Python compile passed; MCP delegate unittest and pytest passed;
  diff whitespace and line-length checks passed; adversarial packet smoke passed;
  `make test-core` passed; independent read-only audit passed; closeout
  resilience check passed
- blocked risks: manual source event false green; synthetic source event false
  green; logging-only Codex JSONL observer promoted to router hook; source event
  packet-kind drift; producer marker drift; claim digest tamper; changed-files
  tamper; write side effects; prompt/browser supplied hook authority; raw prompt,
  raw route id, backend detail, or secret exposure; product-ready or
  native-free-chat claims from source/observation packets
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- tests: `python3 -m unittest tests.test_mcp_delegate` -> 64 tests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"
  python3 -m pytest -q tests/test_mcp_delegate.py` -> 64 passed, 32 subtests
  passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- build: line-length scan for `wild_boar_proxy/mcp_delegate.py` and
  `tests/test_mcp_delegate.py` -> passed
- manual: adversarial packet smoke returned logging-only source event
  `error`, logging-only admission `error`, logging observation
  `native_router_hook_observed=false`, control-boundary source/admission `ok`,
  control observation `native_router_hook_observed=true`, forged manual source
  `source_event_producer_valid=false`, and tampered changed-files source
  `source_event_claim_digest_matched=false`
- manual: independent auditor Herschel confirmed admission requires producer
  packet kind, produced status, producer marker, and matching claim digest;
  logging-only Codex JSONL does not become admitted or observed without control
  boundary evidence; listed false-green classes are blocked
- live verification: no external provider network call was executed in this
  contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_router_hook_source_event`
- packet: `wbp_router_hook_source_admission`
- packet: `wbp_native_router_hook_observation`
- report: success packets prove `source_status=ok`,
  `source_event_packet_kind=wbp_router_hook_source_event`,
  `source_event_producer_valid=true`,
  `source_event_claim_digest_matched=true`,
  `source_control_boundary_proven=true`, `hook_observed_prompt=true`,
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
  provider responses, raw route ids, backend URLs, provider headers, API keys,
  and secret values were not recorded

## Notes

- blockers encountered: no production source-event producer existed; only a
  test-shaped source event dict existed before this contour
- residual risk: claim digest is a packet-integrity guard, not an external
  cryptographic provenance signature; a fully self-consistent forged packet is
  outside this contour's trust boundary
- resume from here: CLOSED
