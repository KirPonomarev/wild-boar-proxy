<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Official MCP Admission Core Proof Closeout

## Goal

Prove the core runtime path for WBP DIP/API-lane delegation through the official
Codex MCP tool approval mechanism, without patching Codex, without
`--dangerously-bypass-approvals-and-sandbox`, and without `danger-full-access`.

## Result

- status: completed
- final verdict: FEATURE_CORE_PROOF_POSITIVE for the tool-directed runtime path;
  native desktop free-chat product UX is explicitly not claimed
- closure state: CLOSED

## Contour Capsule

- goal: prove that Codex can call WBP-owned `delegate_to_dip` through official
  per-tool MCP approval, bind exact alias arguments, and route DIP/Agent 2/custom
  alias work into the API lane with fail-closed negatives
- branch: codex/stabilize-runtime-core
- head: 79f0d0be implementation commit containing the proof runner and targeted tests
- touched files: wild_boar_proxy/official_mcp_admission_proof.py; tests/test_official_mcp_admission_proof.py; wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/official_mcp_admission_core_proof_closeout_2026-06-17.md
- tests run: targeted MCP/proof regression, live official MCP admission matrix, artifact audit, whitespace/compile check, make test-core
- blocked risks: natural soft free-chat prompts are not product-proven; desktop app UX is not product-proven; live external provider dispatch is not claimed; proof uses controlled route-bound API-lane evidence
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py -q` -> 86 passed, 42 subtests passed
- tests: `python3 -m pytest tests/test_official_mcp_admission_proof.py tests/test_mcp_delegate.py tests/test_cli_runner.py -q` -> 107 passed, 42 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` plus `python3 -m compileall -q wild_boar_proxy/official_mcp_admission_proof.py tests/test_official_mcp_admission_proof.py` -> passed
- live verification: `/Volumes/Work/wbp-proof-homes/official-mcp-admission-core-20260617-003226/matrix-packet.json` -> `status=ok`, `final_status=FEATURE_CORE_PROOF_POSITIVE`
- manual: proof artifact audit confirmed command packet semantics for matrix and all case packets, no dangerous modes, no raw recording, and no product/free-chat readiness claim

## Artifacts

- spec: current task thread contour text for Official MCP Admission Proof For DIP/API Lane
- packet: `/Volumes/Work/wbp-proof-homes/official-mcp-admission-core-20260617-003226/matrix-packet.json`
- report: bounded subagent inspector Noether provided read-only file/line surface map for MCP delegate, CLI runner, and tests

Decisive matrix fields:

```json
{
  "status": "ok",
  "final_status": "FEATURE_CORE_PROOF_POSITIVE",
  "positive_aliases_proven": ["DIP", "Agent 2", "Worker"],
  "negative_fail_closed_count": 3,
  "no_dangerous_modes": true,
  "no_raw_recording": true,
  "product_ready": false,
  "native_free_chat_router_proven": false
}
```

## Git

- branch: codex/stabilize-runtime-core
- commit: 79f0d0be for implementation; closeout commit contains this artifact
- pushed: push outcome recorded in task thread final report

## Scope Check

- unrelated work mixed in: No; pre-existing dirty UI files stayed unstaged and unmodified by this contour
- private-data risk reviewed: Yes; runner does not read auth files directly, removes ambient API key env vars, stores sanitized packets, and records no raw prompt/jsonl/backend details

## Notes

- blockers encountered: ambient model admission failed until explicit `gpt-5.4-mini` was configured; natural soft alias prompts did not reliably choose the MCP tool; exact tool-directed prompts with expected alias arguments proved the core runtime path
- resume from here: CLOSED
