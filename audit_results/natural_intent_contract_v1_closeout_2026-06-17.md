<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Natural Intent Contract v1 Closeout

## Goal

Create a strict sanitized contract packet for natural alias intent fixtures so
WBP can represent intent/preflight truth without claiming dispatch, API calls,
Custom Codex hook evidence, or product readiness.

## Result

- status: CLOSED
- final verdict: NATURAL_INTENT_CONTRACT_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: natural phrase fixture to sanitized intent/preflight packet with dispatch explicitly not attempted
- branch: codex/stabilize-runtime-core
- head: f0362449
- touched files: wild_boar_proxy/natural_intent_contract.py; tests/test_natural_intent_contract.py; audit_results/natural_intent_contract_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_natural_intent_contract.py -q; python3 -m pytest tests/test_natural_intent_contract.py tests/test_command_packets_core.py tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py -q; python3 -m compileall -q wild_boar_proxy/natural_intent_contract.py tests/test_natural_intent_contract.py; git diff --check; make test-core; python3 tools/check_closeout_resilience.py audit_results/natural_intent_contract_v1_closeout_2026-06-17.md
- blocked risks: independent audit found a false-green empty-prompt path; fixed with FAIL_PROMPT_EMPTY and regression coverage
- closure state: CLOSED

## Verification

- tests: natural intent contract unit tests passed with 11 tests and 3 subtests
- tests: targeted packet/proof regression passed with 143 tests and 73 subtests
- build: make test-core passed with 418 tests and 120 subtests
- manual: positive fixture packet reports INTENT_PASS while keeping dispatch_status=not_attempted, api_lane_called=false, and product_ready=false
- manual: empty, whitespace, and None prompts report FAIL_PROMPT_EMPTY with prompt_digest_present=false
- audit: read-only auditor reported a blocking empty-prompt false-green finding, and the finding was repaired before closeout

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/natural_intent_contract.py
- report: this closeout

## Evidence Summary

- packet_kind: wbp_natural_intent_contract
- source surfaces admitted: test_fixture, unknown, declared_custom_codex_flow
- source surface not admitted as observed truth: custom_codex_flow
- pass status: INTENT_PASS with PREFLIGHT_PASS only
- dispatch_status: not_attempted
- api_lane_called: false
- dispatch_proven: false
- fallback_used: false
- local_imitation_used: false
- native_codex_subagent_used: false
- product_ready: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- fail-closed statuses covered: FAIL_PROMPT_EMPTY, FAIL_ALIAS_CONTEXT_MISSING, NO_ALIAS_DETECTED, FAIL_ALIAS_NOT_BOUND, FAIL_ALIAS_NOT_API_LANE, FAIL_ROUTE_NOT_ALLOWED, INTENT_AMBIGUOUS_NO_DISPATCH, FAIL_SOURCE_SURFACE_NOT_ADMITTED

## Git

- branch: codex/stabilize-runtime-core
- commit: f0362449 Add natural intent contract packet
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text is represented by digest only, and secret-like fixture strings were removed after pre-commit secret scanning

## Notes

- blockers encountered: empty or whitespace prompt initially produced an ok packet; this was corrected to FAIL_PROMPT_EMPTY before commit.
- resume from here: CLOSED
