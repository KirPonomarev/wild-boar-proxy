<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Live Route-Bound API Smoke Admission Closeout

## Goal

Add an explicit WBP-owned live-smoke admission boundary on top of the existing
route-bound controlled dispatch proof, without changing the ordinary
`delegate_to_dip` no-live behavior, opening network dependencies in core tests,
writing route or credential state, exposing raw backend details, or claiming
product-ready native free-chat routing.

## Result

- status: completed
- final verdict: `wbp_live_route_bound_api_smoke` now admits a fake-transport smoke contract only after route-bound controlled dispatch evidence is valid; it does not claim a real external provider call or live provider response
- closure state: CLOSED

## Contour Capsule

- goal: prove explicit live-smoke admission gating for `delegate_to_dip` evidence while keeping real live provider proof false in the fake-transport core path
- branch: codex/stabilize-runtime-core
- head: 7e0f607fd52c41afd803bcb7d4029b3e932e9c18 pre-closeout base; closure commit includes this evidence and scoped MCP/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/live_route_bound_api_smoke_admission_closeout_2026-06-16.md
- tests run: MCP delegate unittest and pytest passed; Python compile passed; diff whitespace and line-length checks passed; packet sanity probe passed; `make test-core` passed; independent audit and re-check passed; closeout resilience check passed
- blocked risks: fake-transport false-green as real live provider success; browser-supplied route/backend/secret/model authority; raw route id exposure; raw backend detail exposure; secret value exposure; fallback or local imitation; unproven controlled dispatch promotion; credential, transport, and provider error leaks
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_mcp_delegate` -> 46 tests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider" python3 -m pytest -q tests/test_mcp_delegate.py` -> 46 passed, 24 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- build: `git diff --check` -> passed
- build: line-length scan for `wild_boar_proxy/mcp_delegate.py` and `tests/test_mcp_delegate.py` -> passed
- manual: packet sanity probe confirmed admitted fake-smoke packets keep `external_provider_network_used=false`, `live_provider_called=false`, `live_provider_response_proven=false`, `product_ready=false`, and omit the raw route id
- manual: independent auditor Locke found a medium false-green risk in the first fake-transport semantics; the implementation was changed from provider-live proof to fake-transport admission, and the re-check confirmed the risk was resolved
- live verification: no external provider network call was executed in this contour; the admitted path is explicitly `fake_transport_no_external_network`

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_live_route_bound_api_smoke` and `wbp_live_route_bound_api_smoke_proof`
- report: success packets prove the admission contract with `live_smoke_contract_proven=true`, `controlled_dispatch_evidence_proven=true`, `fake_transport_response_proven=true`, `external_provider_network_used=false`, `live_provider_called=false`, `live_provider_response_proven=false`, `fallback_used=false`, `local_imitation_used=false`, `product_ready=false`, and `native_free_chat_router_proven=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped MCP/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, raw prompts, raw provider responses, route secrets, backend URLs, provider headers, API keys, and raw route ids were not recorded

## Notes

- blockers encountered: the first implementation let fake transport set `live_provider_response_proven=true`; audit caught this false-green risk, and the final packet/proof now rejects that claim
- residual risk: tests use temporary fixture IO to create `wbp-agent-runtime-context.json`; this is not a repo, credential, route-registry, evidence, or runtime-state write path
- resume from here: CLOSED
