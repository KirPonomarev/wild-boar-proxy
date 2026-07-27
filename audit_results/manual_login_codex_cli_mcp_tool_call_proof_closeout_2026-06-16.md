<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Manual Login Codex CLI MCP Tool-Call Proof Closeout

## Goal

Check whether Codex CLI can emit a prompt-bound WBP MCP `delegate_to_dip`
tool call after operator login in an isolated proof `CODEX_HOME`, without
patching Codex, touching the real profile, or copying auth material.

## Result

- status: completed
- final verdict: BLOCKED_LOGIN_NOT_COMPLETED; login status exited 0 in the proof home, but both minimal `codex exec` and MCP-targeted `codex exec` failed with auth/login-like admission before any tool-call event
- closure state: CLOSED

## Contour Capsule

- goal: remove the previous no-auth blocker with manual login and test Codex CLI prompt-to-WBP-MCP tool-call behavior
- branch: codex/stabilize-runtime-core
- head: d57f7a1d pre-closeout base; closure commit includes this evidence and scoped parser hardening
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/manual_login_codex_cli_mcp_tool_call_proof_closeout_2026-06-16.md
- tests run: targeted MCP/custom/command-packet tests passed; Python compile passed; line-length and diff whitespace checks passed; `make test-core` passed; closeout resilience check passed before commit
- blocked risks: Codex CLI login status did not translate into admitted `codex exec`; no prompt-bound MCP tool-call event was observed; direct MCP proof stayed separated from product readiness
- closure state: CLOSED

## Verification

- tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_mcp_delegate.py tests/test_custom_agent_bindings.py tests/test_command_packets_core.py` -> 81 passed, 47 subtests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 make test-core` -> 418 passed, 120 subtests passed
- build: `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- build: line-length guard for `wild_boar_proxy/mcp_delegate.py` and `tests/test_mcp_delegate.py` -> passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- manual: operator ran `codex login` with `CODEX_HOME=/Volumes/Work/wbp-proof-homes/codex-mcp-login-20260616-192203`
- live verification: `codex login status` exited 0 for the isolated proof home; stdout and stderr were not recorded
- live verification: WBP MCP registration used the isolated proof home and temp `WBP_PROFILE_DIR`; `codex mcp add`, `codex mcp list`, and `codex mcp get wbp` exited 0
- live verification: direct MCP `delegate_to_dip` returned an ok reality packet with the temp runtime context
- live verification: minimal `codex exec --json` returned exit code 1 with `WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED`
- live verification: MCP-targeted `codex exec --json` returned exit code 1 with `WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED`, `codex_delegate_to_dip_tool_called=false`, and `prompt_to_mcp_call_bound=false`

## Artifacts

- spec: current task thread contour plan
- packet: sanitized live summary below
- report: read-only inspector Popper confirmed scope, bounded proof-home use, auth material guardrails, and unrelated dirty UI files

```json
{
  "auth_files_read": false,
  "bounded_proof_home_used": true,
  "codex_call_machine_error_code": "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
  "codex_delegate_to_dip_tool_called": false,
  "codex_exec_auth_blocker_observed": true,
  "codex_exec_event_types": {
    "error": 1,
    "thread.started": 1,
    "turn.failed": 1,
    "turn.started": 1
  },
  "codex_exec_exit_code": 1,
  "codex_exec_json_events_observed": true,
  "contour_result": "BLOCKED_LOGIN_NOT_COMPLETED",
  "direct_delegate_to_dip_tool_called": true,
  "direct_mcp_reality_packet_status": "ok",
  "login_status_exit_code": 0,
  "mcp_config_visible_to_codex": true,
  "minimal_admission_machine_error_code": "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED",
  "original_profile_touched": false,
  "prompt_to_mcp_call_bound": false,
  "proof_home_tree_listed": false,
  "raw_jsonl_recorded": false,
  "raw_prompt_recorded": false,
  "raw_stderr_recorded": false,
  "secret_value_exposed": false,
  "wiring_result_status": "works_with_limits"
}
```

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped parser/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, proof-home tree, raw Codex JSONL, stderr, prompt text, tokens, route secrets, and backend details were not recorded

## Notes

- blockers encountered: the isolated proof home login did not admit `codex exec` to the model/tool stage, so the contour did not reach a valid no-tool-call decision
- resume from here: CLOSED
