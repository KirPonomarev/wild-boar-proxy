<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Natural Alias Intent Runtime Proof Closeout

## Goal

Check whether natural alias-addressed Codex prompts can make Codex call the
WBP-owned MCP delegate tool without explicit tool-directed wording, while
preserving fail-closed behavior, alias binding, no raw prompt capture, and no
dangerous sandbox modes.

## Result

- status: CLOSED
- final verdict: NATURAL_ALIAS_INTENT_NOT_PROVEN
- closure state: CLOSED

## Contour Capsule

- goal: prove or falsify natural alias intent routing from Codex prompt text into the WBP MCP API lane
- branch: codex/stabilize-runtime-core
- head: 7f4dcacf
- touched files: wild_boar_proxy/official_mcp_admission_proof.py; tests/test_official_mcp_admission_proof.py; audit_results/natural_alias_intent_runtime_proof_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py tests/test_cli_runner.py -q; make test-core; git diff --check; python3 -m compileall -q
- blocked risks: natural alias intent did not produce a Codex MCP tool call in live proof
- closure state: CLOSED

## Verification

- tests: 113 passed and 42 subtests passed for official MCP proof, delegate, and CLI runner targeted tests
- build: make test-core passed with 418 tests and 120 subtests
- manual: proof root inspected for matrix semantics and raw prompt absence
- live verification: /Volumes/Work/wbp-proof-homes/natural-alias-intent-core-20260617-005003/natural-matrix-packet.json

## Artifacts

- spec: current task thread and repository canon
- packet: /Volumes/Work/wbp-proof-homes/natural-alias-intent-core-20260617-005003/natural-matrix-packet.json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_natural_alias_intent_matrix
- status: error
- machine_error_code: WBP_NATURAL_ALIAS_INTENT_NOT_PROVEN
- final_status: NATURAL_ALIAS_INTENT_NOT_PROVEN
- natural_alias_intent_result: red
- case_count: 10
- strict_required_count: 3
- strict_success_count: 0
- strict_tool_call_count: 0
- natural_tool_call_count: 0
- negative_fail_closed_count: 4
- all_required_negatives_fail_closed: true
- ambiguous_case_count: 3
- ambiguous_routed_count: 0
- alias_mismatch_count: 0
- no_dangerous_modes: true
- no_raw_recording: true
- product_ready: false
- native_free_chat_router_proven: false
- runner_auth_files_read: false

## Git

- branch: codex/stabilize-runtime-core
- commit: 7f4dcacf Probe natural alias MCP intent
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; proof records sanitized packet fields and raw prompt search found no matching stored prompt text in the proof root

## Notes

- blockers encountered: natural prompt variants did not cause Codex to invoke the WBP MCP delegate tool in the live matrix.
- resume from here: CLOSED
