<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Safe MCP Admission Proof Closeout

## Goal

Determine whether Codex can safely complete the WBP MCP `delegate_to_dip`
tool-call without `--dangerously-bypass-approvals-and-sandbox`, and localize
the remaining admission boundary if it cannot complete in normal read-only or
workspace-write execution.

## Result

- status: completed
- final verdict: SAFE_ADMISSION_PARTIAL; Codex completed the WBP MCP
  `delegate_to_dip` call without `--dangerously-bypass-approvals-and-sandbox`
  only when `--sandbox danger-full-access` was used, while read-only and
  workspace-write variants reached a tool-call attempt but did not complete the
  MCP call or write WBP evidence
- closure state: CLOSED

## Contour Capsule

- goal: test the smallest available Codex admission knobs for prompt-bound WBP
  MCP completion before any UI, native free-chat router, or Codex patch work
- branch: codex/stabilize-runtime-core
- head: 8790b964 pre-closeout base; closure commit contains this closeout and
  no implementation changes
- touched files: audit_results/safe_mcp_admission_proof_closeout_2026-06-16.md
- tests run: targeted MCP/CLI runner tests passed; `make test-core` passed;
  diff whitespace check passed; closeout resilience check passed before commit
- blocked risks: read-only and workspace-write Codex exec modes still fail to
  complete the MCP call; `danger-full-access` is diagnostic/high-risk and is
  not product-ready safe admission; live provider response was not required or
  proven; native free-chat product routing was not proven
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_mcp_delegate.py tests/test_cli_runner.py -q` -> 102 passed, 42 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check` -> passed
- live verification: broad sanitized matrix under `/Volumes/Work/wbp-proof-homes/safe-mcp-admission-matrix-20260616-235837` tested read-only default, read-only `approval_policy=never`, top-level `-a never`, trusted repo read-only, workspace-write, and danger-full-access variants
- live verification: focused sanitized matrix under `/Volumes/Work/wbp-proof-homes/safe-mcp-admission-focused-20260617-000147` tested no-evidence read-only, evidence-inside-workdir workspace-write, `--add-dir` workspace-write, danger-full-access with default approval, danger-full-access with config `approval_policy=never`, and read-only disk-full-read permission
- manual: read-only inspector Ohm found no local explicit MCP-specific approval/trust flag in CLI help/config; clean `CODEX_HOME` feature listing showed `tool_call_mcp_elicitation=true`, `guardian_approval=true`, and `exec_permission_approvals=false`

## Artifacts

- spec: current task thread contour text and canon-bound execution instructions
- packet: sanitized live matrix summaries below
- report: read-only inspector Ohm reviewed local CLI/config/docs only, without reading auth files or secrets

Broad matrix decisive rows:

```json
[
  {
    "variant": "disposable_readonly_default",
    "sandbox": "read-only",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false,
    "blocking_reasons": [
      "codex_delegate_to_dip_tool_call_not_completed",
      "codex_delegate_to_dip_tool_call_failed"
    ]
  },
  {
    "variant": "disposable_readonly_top_ask_never",
    "sandbox": "read-only",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false,
    "blocking_reasons": [
      "codex_delegate_to_dip_tool_call_not_completed",
      "codex_delegate_to_dip_tool_call_failed"
    ]
  },
  {
    "variant": "trusted_repo_readonly_top_ask_never",
    "sandbox": "read-only",
    "workdir_kind": "repo",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false,
    "blocking_reasons": [
      "codex_delegate_to_dip_tool_call_not_completed",
      "codex_delegate_to_dip_tool_call_failed"
    ]
  },
  {
    "variant": "disposable_workspace_write_top_ask_never",
    "sandbox": "workspace-write",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false,
    "blocking_reasons": [
      "codex_delegate_to_dip_tool_call_not_completed",
      "codex_delegate_to_dip_tool_call_failed"
    ]
  },
  {
    "variant": "disposable_danger_full_top_ask_never",
    "sandbox": "danger-full-access",
    "diagnostic_only": true,
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": true,
    "evidence_file_written": true,
    "evidence_status": "ok",
    "evidence_alias_context_read": true,
    "evidence_api_lane_called": true,
    "evidence_route_bound_dispatch_proven": true,
    "evidence_fallback_used": false,
    "evidence_local_imitation_used": false,
    "prompt_to_mcp_call_bound": true
  }
]
```

Focused matrix decisive rows:

```json
[
  {
    "variant": "readonly_no_evidence_top_ask_never",
    "sandbox": "read-only",
    "evidence_location": "none",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false
  },
  {
    "variant": "workspace_write_evidence_workdir_top_ask_never",
    "sandbox": "workspace-write",
    "evidence_location": "workdir",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false
  },
  {
    "variant": "workspace_write_evidence_vroot_add_vroot_top_ask_never",
    "sandbox": "workspace-write",
    "add_dirs": [
      "vroot"
    ],
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false
  },
  {
    "variant": "danger_full_default_approval",
    "sandbox": "danger-full-access",
    "diagnostic_only": true,
    "codex_tool_call_completed": true,
    "evidence_file_written": true,
    "evidence_status": "ok",
    "evidence_alias_context_read": true,
    "evidence_api_lane_called": true,
    "evidence_route_bound_dispatch_proven": true,
    "evidence_fallback_used": false,
    "evidence_local_imitation_used": false
  },
  {
    "variant": "readonly_disk_full_read_permission",
    "sandbox": "read-only",
    "codex_tool_call_attempted": true,
    "codex_tool_call_completed": false,
    "evidence_file_written": false
  }
]
```

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, raw Codex JSONL, raw prompt text, MCP tool arguments, plaintext route id, backend raw details, provider raw response, and secrets were not recorded in committed evidence

## Notes

- blockers encountered: no local CLI/config surface exposed a narrower MCP-specific trust flag; read-only and workspace-write modes failed before WBP evidence was written, while danger-full-access completed WBP evidence without the dangerous bypass flag
- resume from here: CLOSED
