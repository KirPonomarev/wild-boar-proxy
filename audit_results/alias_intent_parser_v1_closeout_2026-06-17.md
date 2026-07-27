<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Alias Intent Parser v1 Closeout

## Goal

Add a small deterministic WBP-owned parser that extracts an alias candidate
from natural prompt text using only the server-issued runtime context, then
feeds that candidate into the existing natural intent contract packet without
dispatching, calling API lanes, proving Custom Codex origin, or claiming product
readiness.

## Result

- status: CLOSED
- final verdict: ALIAS_INTENT_PARSER_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: natural prompt text to context-only alias candidate to sanitized intent/preflight packet with dispatch explicitly not attempted
- branch: codex/stabilize-runtime-core
- head: 14bc4179
- touched files: wild_boar_proxy/natural_intent_contract.py; tests/test_natural_intent_contract.py; audit_results/alias_intent_parser_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_natural_intent_contract.py -q; python3 -m pytest tests/test_natural_intent_contract.py tests/test_command_packets_core.py tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py -q; python3 -m pytest tests/test_custom_agent_bindings.py tests/test_natural_intent_contract.py -q; python3 -m compileall -q wild_boar_proxy tests/test_natural_intent_contract.py; make test-core; git diff --check; python3 tools/check_closeout_resilience.py audit_results/alias_intent_parser_v1_closeout_2026-06-17.md
- blocked risks: primary-plus-api phrase handling was separated from multi-target ambiguity so the core phrase Codex to DIP can parse while DIP plus Worker remains fail-closed
- closure state: CLOSED

## Verification

- tests: natural intent contract unit tests passed with 22 tests and 12 subtests
- tests: targeted packet and MCP boundary regression passed with 154 tests and 82 subtests
- tests: custom agent binding plus natural intent contract regression passed with 37 tests and 23 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output
- live verification: not performed; this contour is parser/preflight only and does not attempt live provider or Custom Codex dispatch proof

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/natural_intent_contract.py
- report: this closeout

## Evidence Summary

- parser entrypoint: build_natural_intent_parser_packet
- pure parser entrypoint: parse_natural_alias_intent
- packet_kind: wbp_natural_intent_contract
- parser status values: PARSER_MATCHED, PARSER_NO_ALIAS, PARSER_AMBIGUOUS, PARSER_CONTEXT_MISSING, PARSER_PROMPT_EMPTY
- alias match status values: ALIAS_MATCH_EXACT, ALIAS_MATCH_NONE, ALIAS_MATCH_AMBIGUOUS
- target phrase covered: Codex, дай задачу DIP
- primary address plus one API target: selected as API target candidate only
- multiple API aliases for one target: blocked as INTENT_AMBIGUOUS_NO_DISPATCH
- unknown alias: blocked as NO_ALIAS_DETECTED because the parser does not guess aliases outside context
- primary-only alias: recognized but blocked as FAIL_ALIAS_NOT_API_LANE
- empty prompt: blocked as FAIL_PROMPT_EMPTY
- invalid context: blocked as FAIL_ALIAS_CONTEXT_MISSING
- dispatch_status: not_attempted
- api_lane_called: false
- dispatch_proven: false
- fallback_used: false
- local_imitation_used: false
- native_codex_subagent_used: false
- product_ready: false
- native_free_chat_router_proven: false
- prompt_text_recorded: false
- raw_prompt_recorded: false
- parser_prompt_text_recorded: false
- parser_raw_prompt_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false

## Independent Review

- Helmholtz read-only scanner identified the narrow integration point in natural_intent_contract.py and confirmed the existing tests did not yet cover deterministic parsing from prompt_text.
- Russell read-only auditor identified the main guardrails: no UI, no dispatch claim, no provider truth, no raw prompt, no browser authority, no product readiness.
- Operator verification was performed locally after both reports; agent claims were not treated as closure evidence without local command output.

## Git

- branch: codex/stabilize-runtime-core
- commit: alias parser v1 closeout commit created after verification
- pushed: branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; parser packets retain prompt digest and safe alias metadata only, and targeted redaction tests cover secret-like and backend-like prompt content

## Notes

- blockers encountered: the first no-alias negative test used Codex in the prompt and correctly hit FAIL_ALIAS_NOT_API_LANE; the test was corrected to a prompt with no context alias. Final audit found missing direct coverage for ambiguity branches; multiple API targets, overlapping aliases for different agents, and multiple non-API aliases are now covered.
- resume from here: CLOSED
