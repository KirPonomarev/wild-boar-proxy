<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Router Hook Entry v1 Closeout

## Goal

Add a minimal WBP-owned probe surface that accepts a natural prompt, reads the
server-issued runtime context, invokes the natural alias parser/preflight
packet, and emits strict JSON evidence that the hook entry was observed without
dispatching, calling API lanes, starting Codex, or claiming product readiness.

## Result

- status: CLOSED
- final verdict: ROUTER_HOOK_ENTRY_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: Custom-Codex-oriented prompt to WBP-owned hook entry to parser/preflight packet with dispatch explicitly not attempted
- branch: codex/stabilize-runtime-core
- head: 4a33f986
- touched files: wild_boar_proxy/router_hook_entry.py; wild_boar_proxy/cli.py; tests/test_router_hook_entry.py; audit_results/router_hook_entry_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_router_hook_entry.py -q; python3 -m pytest tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_command_packets_core.py tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py -q; python3 -m pytest tests/test_owner_surface_effect_inventory.py tests/test_router_hook_entry.py -q; python3 -m pytest tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m compileall -q wild_boar_proxy tests/test_router_hook_entry.py; make test-core; git diff --check
- blocked risks: independent audit found hook_entry_proven overclaim on error packets and missing context/route negative coverage; fixed with hook_entry_proven=ok and explicit negative tests
- closure state: CLOSED

## Verification

- tests: router hook entry focused tests passed with 13 tests and 5 subtests
- tests: targeted parser packet and MCP boundary regression passed with 167 tests and 87 subtests
- tests: owner surface effect inventory plus hook entry passed with 38 tests and 42 subtests
- tests: CLI effect classifier targeted case passed with 1 test and 59 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output
- manual: local router-hook entry command emitted status ok, packet_kind wbp_router_hook_entry, alias_candidate DIP, INTENT_PASS, PREFLIGHT_PASS, dispatch_status not_attempted, api_lane_called false, and product_ready false
- audit: Feynman and Harvey read-only reviews passed after the overclaim and missing-negative findings were repaired
- live verification: not performed; this contour is hook-entry/preflight only and does not attempt provider or Custom Codex dispatch proof

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/router_hook_entry.py
- command: wild-boar-proxy router-hook entry --prompt <natural prompt> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_router_hook_entry
- command surface: router-hook entry --json
- effect: probe
- changed_files: []
- hook_source_kind: wbp_owned_router_hook_entry
- hook_entry_observed: true on admitted local hook entry
- hook_entry_proven: true only when hook surface is admitted and parser/preflight packet is ok
- hook_surface_can_dispatch: false
- hook_dispatch_attempted: false
- parser_packet_kind: wbp_natural_intent_contract
- source_surface: declared_custom_codex_flow
- source_surface_observed: false
- command_origin_proven: false
- custom_codex_origin_proven: false
- native_custom_codex_flow_proven: false
- native_router_hook_observed: false
- dispatch_status: not_attempted
- api_lane_called: false
- dispatch_proven: false
- fallback_used: false
- local_imitation_used: false
- native_codex_subagent_used: false
- native_codex_subagent_used_as_dip: false
- product_ready: false
- native_free_chat_router_proven: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- browser_can_supply_hook_authority: false
- browser_can_supply_prompt_authority: false
- browser_can_supply_route_authority: false

## Negative Coverage

- no alias: blocked without dispatch
- primary-only alias: blocked as not API lane
- unadmitted hook surface: blocked even when parser would pass
- empty prompt: blocked without hook proof
- route outside allowlist: blocked
- forbidden stale route: blocked
- missing runtime context file: blocked
- malformed runtime context JSON: blocked
- runtime context JSON that is not a mapping: blocked
- error packets: do not claim hook_entry_proven

## Git

- branch: codex/stabilize-runtime-core
- commit: router hook entry v1 commit created after verification
- pushed: branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text is represented by digest through the parser packet, runtime context file paths are not recorded, and no secret/backend prompt content is emitted

## Notes

- blockers encountered: initial hook_entry_proven was too broad and became true on parser/preflight error packets; this was repaired before closeout. Initial negative matrix lacked an explicit forbidden stale route case; this was repaired before closeout.
- resume from here: CLOSED
