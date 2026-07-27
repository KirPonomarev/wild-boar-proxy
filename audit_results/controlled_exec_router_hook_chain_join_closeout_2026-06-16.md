<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Controlled Exec Router-Hook Chain Join Closeout

## Goal

Join the controlled exec submit boundary, Codex MCP tool-call observation, and
router-hook source admission into one strict packet without claiming API-lane
provider dispatch, product readiness, native free-chat routing, or storing raw
prompt/JSONL/tool-argument material.

## Result

- status: completed
- final verdict: `wbp_controlled_exec_router_hook_chain` now proves only a
  normalized packet chain with pre-process submit evidence, post-process Codex
  observation evidence, producer provenance, matching claim digests, bounded
  sequence markers, and fail-closed raw/product/native/API overclaim guards
- closure state: CLOSED

## Contour Capsule

- goal: prove the controlled exec router-hook evidence chain at packet level
  without moving into UI, live-provider dispatch, Codex patching, or effective
  runtime writes
- branch: codex/stabilize-runtime-core
- head: 4f647da781fb85356a6d98aeb38430211884c4e5 pre-closeout base; closure
  commit includes this evidence and scoped MCP/runner/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; wild_boar_proxy/cli_runner.py;
  tests/test_mcp_delegate.py; tests/test_cli_runner.py;
  audit_results/controlled_exec_router_hook_chain_join_closeout_2026-06-16.md
- tests run: Python compile passed; targeted MCP delegate tests passed;
  command-packet and CLI-runner targeted tests passed; `make test-core` passed;
  diff whitespace check passed; independent read-only inspections completed;
  closeout resilience check passed
- blocked risks: missing submit-boundary packet; manual submit-boundary packet;
  tampered submit-boundary digest; missing or wrong submit sequence; missing,
  forged, tampered, no-delegate, or subagent-shaped Codex observation packet;
  prompt mismatch; raw prompt, raw JSONL, tool arguments, raw route id, backend
  detail, or secret exposure; local imitation; fallback; API-lane call claim;
  product-ready or native-free-chat claim
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py
  wild_boar_proxy/cli_runner.py tests/test_mcp_delegate.py
  tests/test_cli_runner.py` -> passed
- tests: `python3 -m pytest tests/test_mcp_delegate.py -q` -> 79 passed, 42
  subtests passed
- tests: `python3 -m pytest tests/test_command_packets_core.py
  tests/test_cli_runner.py -q` -> 61 passed, 28 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py
  wild_boar_proxy/cli_runner.py tests/test_mcp_delegate.py
  tests/test_cli_runner.py` -> passed
- manual: inspector Socrates confirmed the minimal production scope is a thin
  normalized-packet wrapper over submit-boundary, Codex observation, and
  router-hook admission packets, not raw prompt/JSONL processing
- manual: auditor Dewey found a blocking forged-Codex-packet provenance gap;
  the contour was corrected with Codex observation producer provenance, claim
  digest validation, and a forged/tampered packet regression test
- live verification: no external provider network call was executed in this
  contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_controlled_exec_router_hook_chain`
- packet: `wbp_exec_wrapper_submit_boundary_probe`
- packet: `wbp_codex_exec_tool_call_observation`
- packet: `wbp_router_hook_control_boundary`
- packet: `wbp_router_hook_source_event`
- packet: `wbp_router_hook_source_admission`
- report: success packets prove `submit_boundary_sequence=pre_process_start`,
  `codex_observation_sequence=post_process_start`,
  `controlled_exec_sequence_proven=true`, `submit_boundary_packet_ok=true`,
  `codex_tool_call_observation_packet_ok=true`,
  `codex_tool_call_observation_claim_digest_matched=true`,
  `prompt_to_submit_boundary_bound=true`, `prompt_to_mcp_call_bound=true`,
  `control_boundary_proven=true`, `source_event_produced=true`,
  `source_admitted=true`, `api_lane_called=false`, `product_ready=false`, and
  `native_free_chat_router_proven=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped MCP/runner/test
  changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged
  and untouched
- private-data risk reviewed: auth files, raw prompts, raw transcripts, raw
  JSONL, raw tool arguments, raw provider responses, raw route ids, backend
  URLs, provider headers, API keys, and secret values were not recorded

## Notes

- blockers encountered: the first chain builder accepted a forged Codex
  observation dictionary with manually set green booleans; it now requires
  `producer_built_by=build_codex_exec_tool_call_observation_packet` and a
  matching `codex_tool_call_claim_sha256`
- residual risk: claim digests are packet-integrity guards, not external
  cryptographic provenance signatures; this contour proves controlled exec
  router-hook chain evidence only, not completed native free-chat product
  routing or provider API dispatch
- resume from here: CLOSED
