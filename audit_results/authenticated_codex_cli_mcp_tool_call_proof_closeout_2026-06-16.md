<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Authenticated Codex CLI MCP Tool-Call Proof Closeout

## Goal

Test whether a bounded Codex CLI run can load the WBP MCP server and emit a
prompt-bound `delegate_to_dip` tool call without patching Codex or touching the
real Codex profile.

## Result

- status: completed
- final verdict: BLOCKED_AUTH; temp Codex MCP config loaded and direct WBP MCP `delegate_to_dip` worked, but `codex exec --json` stopped at auth/admission before a prompt-bound tool-call event
- closure state: CLOSED

## Contour Capsule

- goal: prove or block the official Codex CLI MCP/tool path for a prompt-bound WBP `delegate_to_dip` call using temp profiles only
- branch: codex/stabilize-runtime-core
- head: 39afa2a8 pre-closeout base; closure commit adds this completed evidence only
- touched files: audit_results/authenticated_codex_cli_mcp_tool_call_proof_closeout_2026-06-16.md
- tests run: targeted MCP/custom/command-packet tests passed; `make test-core` passed; closeout resilience check passed before commit
- blocked risks: auth/admission unavailable in env; prompt-bound Codex MCP tool-call not observed; direct MCP proof kept separate from product readiness
- closure state: CLOSED

## Verification

- tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_mcp_delegate.py tests/test_custom_agent_bindings.py tests/test_command_packets_core.py` -> 81 passed, 42 subtests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 make test-core` -> 418 passed, 120 subtests passed
- build: no code files changed in this contour
- manual: temp `CODEX_HOME` and temp `WBP_PROFILE_DIR` were used; `CODEX_API_KEY_present=false`, `OPENAI_API_KEY_present=false`, and original profile access was not required
- live verification: `codex mcp add`, `codex mcp list`, and `codex mcp get wbp` all exited 0 in the temp Codex profile
- live verification: direct MCP `delegate_to_dip` returned an ok reality packet
- live verification: `codex exec --json --ephemeral --sandbox read-only --ignore-rules` was invoked against the temp profile and returned exit code 1 with auth/admission blocking classified as `WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED`

## Artifacts

- spec: current task thread contour plan
- packet: sanitized live summary below
- report: read-only inspector Singer confirmed scope, secret hygiene, and unrelated dirty UI files

```json
{
  "api_lane_called": false,
  "auth_env_present": false,
  "codex_call_machine_error_code": "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
  "codex_cli_prompt_mcp_tool_call_proven": false,
  "codex_delegate_to_dip_tool_called": false,
  "codex_exec_authorized": false,
  "codex_exec_exit_code": 1,
  "codex_exec_invoked": true,
  "codex_exec_json_events_observed": true,
  "contour_result": "BLOCKED_AUTH",
  "direct_delegate_to_dip_tool_called": true,
  "direct_mcp_reality_packet_status": "ok",
  "fallback_used": false,
  "local_imitation_used": false,
  "mcp_config_visible_to_codex": true,
  "native_free_chat_router_proven": false,
  "original_profile_touched": false,
  "product_ready": false,
  "prompt_hash_matches_tool_args": false,
  "prompt_to_mcp_call_bound": false,
  "raw_backend_details_exposed": false,
  "raw_jsonl_recorded": false,
  "raw_prompt_recorded": false,
  "raw_stderr_recorded": false,
  "secret_value_exposed": false,
  "temp_codex_home_used": true,
  "temp_wbp_profile_dir_used": true,
  "tool_call_event_observed": false,
  "wiring_result_status": "works_with_limits"
}
```

## Git

- branch: codex/stabilize-runtime-core
- commit: closure evidence commit containing this closeout only
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left untouched
- private-data risk reviewed: raw Codex JSONL, stderr, prompt text, tokens, auth files, route secrets, and backend details were not recorded

## Notes

- blockers encountered: safe auth/admission was unavailable in the environment, so Codex CLI did not reach a prompt-bound MCP tool-call decision
- resume from here: CLOSED
