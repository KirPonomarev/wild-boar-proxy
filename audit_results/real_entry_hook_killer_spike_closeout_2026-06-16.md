<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Real Entry Hook Killer Spike Closeout

## Goal

Determine whether a real Codex prompt can cross into a WBP-owned MCP
`delegate_to_dip` hook and whether that hook can read the Custom Codex runtime
context, resolve `DIP` to the API lane, and produce route-bound controlled
dispatch evidence without local imitation.

## Result

- status: completed
- final verdict: PARTIAL_PROVEN; ordinary non-interactive read-only `codex exec`
  reached a `delegate_to_dip` MCP-call attempt but did not complete the MCP
  call, while a disposable explicit admission-bypass run completed the real WBP
  MCP call and produced sanitized WBP evidence for alias context, API-lane
  binding, allowlist enforcement, and route-bound controlled dispatch
- closure state: CLOSED

## Contour Capsule

- goal: prove or block the narrow entry-hook hypothesis before expanding any
  UI, native free-chat router, or Codex patch surface
- branch: codex/stabilize-runtime-core
- head: 9f5c788f pre-closeout base; closure commit contains the scoped observer
  hardening, sanitized evidence sink, test coverage, and this closeout
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py;
  audit_results/real_entry_hook_killer_spike_closeout_2026-06-16.md
- tests run: Python compile passed; `tests/test_mcp_delegate.py` passed;
  `tests/test_mcp_delegate.py tests/test_cli_runner.py` passed;
  `make test-core` passed; diff whitespace check passed; closeout resilience
  check passed before commit
- blocked risks: ordinary read-only non-interactive Codex exec still does not
  complete the MCP tool call without explicit approval bypass; live provider
  response was not proven; native free-chat product routing was not proven
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- tests: `python3 -m pytest tests/test_mcp_delegate.py -q` -> 81 passed, 42 subtests passed
- tests: `python3 -m pytest tests/test_mcp_delegate.py tests/test_cli_runner.py -q` -> 102 passed, 42 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- manual: independent read-only inspector Ramanujan confirmed failed MCP calls are no longer counted as success and confirmed the read-only versus admission-bypass proof split
- live verification: disposable read-only canonical context proof observed Codex attempting `delegate_to_dip`, but the MCP call did not complete and no WBP evidence file was written
- live verification: disposable explicit admission-bypass canonical context proof completed the WBP MCP call and wrote sanitized WBP evidence with alias context read, API lane called, route-bound dispatch proven, no fallback, and no local imitation

## Artifacts

- spec: current task thread contour text and canon-bound execution instructions
- packet: sanitized live summaries below
- report: independent read-only inspector Ramanujan reviewed the diff and proof summaries without editing files or reading auth material

Read-only non-bypass canonical context summary:

```json
{
  "blocking_reasons": [
    "codex_delegate_to_dip_tool_call_not_completed",
    "codex_delegate_to_dip_tool_call_failed"
  ],
  "codex_delegate_to_dip_tool_called": false,
  "codex_exec_exit_code": 0,
  "codex_machine_error_code": "WBP_CODEX_EXEC_TOOL_CALL_NOT_PROVEN",
  "codex_packet_status": "error",
  "codex_tool_call_attempted": true,
  "codex_tool_call_completed": false,
  "codex_tool_call_failed": true,
  "evidence_file_written": false,
  "prompt_to_mcp_call_bound": false,
  "proof_root": "/Volumes/Work/wbp-proof-homes/entry-hook-readonly-canonical-20260616-234756",
  "raw_jsonl_recorded": false,
  "raw_prompt_recorded": false,
  "variant": "read_only_canonical_context_no_bypass"
}
```

Explicit admission-bypass canonical context summary:

```json
{
  "blocking_reasons": [],
  "codex_delegate_to_dip_tool_called": true,
  "codex_exec_exit_code": 0,
  "codex_machine_error_code": "OK",
  "codex_packet_status": "ok",
  "codex_tool_call_attempted": true,
  "codex_tool_call_completed": true,
  "codex_tool_call_failed": false,
  "evidence_alias_context_read": true,
  "evidence_allowed_api_route_ids_enforced": true,
  "evidence_api_lane_called": true,
  "evidence_api_lane_dispatch_admitted": true,
  "evidence_coding_alias_bound_to_api_lane": true,
  "evidence_controlled_provider_response_proven": true,
  "evidence_custom_codex_agent_runtime_context_proven": true,
  "evidence_delegate_to_dip_tool_called": true,
  "evidence_fallback_used": false,
  "evidence_file_written": true,
  "evidence_forbidden_stale_route_ids_enforced": true,
  "evidence_live_provider_response_proven": false,
  "evidence_local_imitation_used": false,
  "evidence_machine_error_code": "OK",
  "evidence_native_free_chat_router_proven": false,
  "evidence_no_secret_exposed": true,
  "evidence_product_ready": false,
  "evidence_provider_response_proven": true,
  "evidence_route_allowed": true,
  "evidence_route_bound_dispatch_proven": true,
  "evidence_runtime_context_file_proven": true,
  "evidence_selected_alias": "DIP",
  "evidence_selected_alias_lane": "api_route",
  "evidence_selected_api_route_id_present": true,
  "evidence_status": "ok",
  "prompt_to_mcp_call_bound": true,
  "proof_root": "/Volumes/Work/wbp-proof-homes/entry-hook-bypass-canonical-20260616-234713",
  "raw_jsonl_recorded": false,
  "raw_prompt_recorded": false,
  "variant": "dangerously_bypass_approvals_and_sandbox_canonical_context_disposable"
}
```

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped command-contract changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, raw Codex JSONL, raw prompt text, MCP tool arguments, plaintext route id, backend raw details, provider raw response, and secrets were not recorded in committed evidence

## Notes

- blockers encountered: ordinary read-only non-interactive Codex exec cancelled or failed the MCP tool call before WBP evidence was written; explicit admission bypass completed the MCP call in a disposable workdir/profile
- resume from here: CLOSED
