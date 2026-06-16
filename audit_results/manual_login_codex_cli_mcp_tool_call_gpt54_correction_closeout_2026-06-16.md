<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Manual Login Codex CLI MCP Tool-Call GPT-5.4 Correction Closeout

## Goal

Resolve the isolated Codex CLI admission mismatch and retest whether an
admitted Codex CLI run can emit a prompt-bound WBP MCP `delegate_to_dip` tool
call.

## Result

- status: completed
- final verdict: PROVEN by live `codex exec --json -m gpt-5.4` evidence; the previous blocker was the default `gpt-5.3-codex` model being unsupported for ChatGPT-account Codex exec, and explicit `-m gpt-5.4` produced a prompt-bound WBP MCP tool call
- closure state: CLOSED

## Contour Capsule

- goal: correct the previous manual-login admission result by using an admitted ChatGPT-account model and prove or block prompt-bound WBP MCP tool-call behavior
- branch: codex/stabilize-runtime-core
- head: 91bb2e4a pre-correction base; correction commit includes this evidence and scoped classifier/test hardening
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/manual_login_codex_cli_mcp_tool_call_gpt54_correction_closeout_2026-06-16.md
- tests run: targeted MCP/custom/command-packet tests passed; Python compile passed; line-length and diff whitespace checks passed; `make test-core` passed; closeout resilience check passed before commit
- blocked risks: default Codex CLI model was incompatible with ChatGPT-account exec; broad auth classifier initially over-classified successful ChatGPT-account output; direct MCP proof was kept as prerequisite evidence only, not the basis for `PROVEN`
- closure state: CLOSED

## Verification

- tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_mcp_delegate.py tests/test_custom_agent_bindings.py tests/test_command_packets_core.py` -> 82 passed, 47 subtests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 make test-core` -> 418 passed, 120 subtests passed
- build: `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- build: line-length guard for `wild_boar_proxy/mcp_delegate.py` and `tests/test_mcp_delegate.py` -> passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- live verification: sanitized error extraction showed default `gpt-5.3-codex` is not supported when using Codex with a ChatGPT account
- live verification: model admission matrix showed `gpt-5.4` completed a minimal `codex exec --json` with exit code 0
- live verification: WBP MCP registration prerequisite used the isolated proof home and temp `WBP_PROFILE_DIR`; `codex mcp add`, `codex mcp list`, and `codex mcp get wbp` exited 0
- live verification: direct MCP `delegate_to_dip` prerequisite returned an ok reality packet with the temp runtime context, but direct proof alone was not treated as `PROVEN`
- live verification: decisive proof was `codex exec --json -m gpt-5.4` observing `mcp_tool_call` item events, server `wbp`, tool `delegate_to_dip`, matching prompt/tool-argument hash, and exit code 0

## Artifacts

- spec: current task thread diagnostic continuation
- packet: sanitized live summary below
- report: read-only inspector Copernicus identified the status/admission distinction and global config risk without reading auth material

```json
{
  "auth_files_read": false,
  "bounded_proof_home_used": true,
  "codex_call_machine_error_code": "OK",
  "codex_delegate_to_dip_tool_called": true,
  "codex_exec_auth_blocker_observed": false,
  "codex_exec_event_summary": {
    "event_types": {
      "item.completed": 3,
      "item.started": 1,
      "thread.started": 1,
      "turn.completed": 1,
      "turn.started": 1
    },
    "item_types": {
      "agent_message": 2,
      "item.completed": 3,
      "item.started": 1,
      "mcp_tool_call": 2,
      "thread.started": 1,
      "turn.completed": 1,
      "turn.started": 1
    },
    "parse_error_count": 0,
    "server_names_observed": [
      "wbp"
    ]
  },
  "codex_exec_exit_code": 0,
  "codex_exec_json_events_observed": true,
  "contour_result": "PROVEN",
  "decisive_proof_basis": "codex_exec_prompt_bound_mcp_tool_call",
  "direct_delegate_to_dip_tool_called": true,
  "direct_mcp_only_would_not_be_proven": true,
  "direct_mcp_reality_packet_status": "ok",
  "mcp_config_visible_to_codex": true,
  "minimal_admission_auth_blocker_observed": false,
  "minimal_admission_exec_exit_code": 0,
  "model_override": "gpt-5.4",
  "original_profile_touched": false,
  "prompt_hash_matches_tool_args": true,
  "prompt_to_mcp_call_bound": true,
  "proof_home_tree_listed": false,
  "raw_jsonl_recorded": false,
  "raw_prompt_recorded": false,
  "raw_stderr_recorded": false,
  "secret_value_exposed": false,
  "tool_call_event_observed": true,
  "tool_name": "delegate_to_dip",
  "wiring_result_status": "proven"
}
```

## Git

- branch: codex/stabilize-runtime-core
- commit: correction commit containing this closeout and scoped parser/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, proof-home tree, raw Codex JSONL, stderr, prompt text, tokens, route secrets, and backend details were not recorded

## Notes

- blockers encountered: default model admission failed for ChatGPT-account exec; explicit `gpt-5.4` resolved admission and allowed the MCP tool-call proof to run
- resume from here: CLOSED
