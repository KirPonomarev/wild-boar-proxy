<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Exec Wrapper Submit Boundary Producer Closeout

## Goal

Create a real WBP-owned boundary-evidence producer on one existing controlled
submit entrypoint, then prove that manual or post-factum evidence can no longer
turn the router hook control boundary green.

## Result

- status: completed
- final verdict: `wbp_exec_wrapper_submit_boundary_probe` is now produced by
  `build_exec_wrapper_submit_boundary_probe_packet` and integrated into the
  bounded CLI exec wrapper before `run_bounded_process`; router hook control
  boundary admission now requires producer status, final status, marker, and a
  matching submit-boundary claim digest
- closure state: CLOSED

## Contour Capsule

- goal: prove a scoped WBP-owned pre-Codex submit boundary for controlled
  `codex exec ... -` runs without claiming native free-chat product routing
- branch: codex/stabilize-runtime-core
- head: 4ae1b5c92677b6b9757262098f6a2d16380045a2 pre-closeout base; closure
  commit includes this evidence and scoped MCP/runner/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; wild_boar_proxy/cli_runner.py;
  tests/test_mcp_delegate.py; tests/test_cli_runner.py;
  audit_results/exec_wrapper_submit_boundary_producer_closeout_2026-06-16.md
- tests run: Python compile passed; targeted MCP/CLI pytest passed; diff
  whitespace and added-line checks passed; adversarial packet smoke passed;
  `make test-core` passed; independent read-only audits completed; closeout
  resilience check passed
- blocked risks: manual submit-boundary evidence false green; post-factum JSONL
  evidence promoted to pre-Codex boundary; missing delegate route contract;
  claim digest tamper; changed-files tamper; prompt/browser supplied authority;
  effective runtime/config/profile/route/credential writes; raw prompt, raw
  route id, backend detail, or secret exposure; product-ready or
  native-free-chat claims from producer/boundary/source packets
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py
  wild_boar_proxy/cli_runner.py tests/test_mcp_delegate.py
  tests/test_cli_runner.py` -> passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"
  python3 -m pytest -q tests/test_mcp_delegate.py tests/test_cli_runner.py`
  -> 93 passed, 32 subtests passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py
  wild_boar_proxy/cli_runner.py tests/test_mcp_delegate.py
  tests/test_cli_runner.py` -> passed
- build: added-line length scan for scoped files -> passed
- manual: adversarial packet smoke returned producer `PASS`, temp-write
  declaration `PASS`, control-boundary chain `PASS`, source-event chain `PASS`,
  missing route contract blocked `PASS`, manual evidence blocked `PASS`,
  post-factum evidence blocked `PASS`, tamper blocked `PASS`, and unsafe
  raw/secret/product claims blocked `PASS`
- manual: inspector Mill confirmed public MCP `tools/call` is after Codex tool
  selection and is not the pre-decision boundary; its negative-test gap report
  was used to harden the producer and builder tests
- manual: auditor Faraday confirmed producer fail-closed behavior, manual
  evidence rejection, and pre-`run_bounded_process` creation; its temp-write
  ambiguity finding was remediated with explicit `owned_temp_config_written`,
  `owned_temp_output_file_reserved`, and `effective_config_written=false`
  fields plus assertions
- live verification: no external provider network call was executed in this
  contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_exec_wrapper_submit_boundary_probe`
- packet: `wbp_router_hook_control_boundary`
- packet: `wbp_router_hook_source_event`
- report: success packets prove `submit_boundary_status=ok`,
  `entrypoint_kind=codex_cli_runner_stdin_submit`,
  `control_boundary_wbp_owned=true`,
  `control_boundary_observed_prompt=true`,
  `control_boundary_pre_codex_decision=true`,
  `control_boundary_post_factum_only=false`,
  `control_boundary_can_enforce_router=true`,
  `control_boundary_can_route_delegate_to_dip=true`,
  `submit_boundary_claim_digest_present=true`,
  `control_boundary_evidence_packet_ok=true`,
  `control_boundary_evidence_producer_valid=true`,
  `control_boundary_evidence_claim_digest_matched=true`,
  `owned_temp_config_written=true`, `effective_config_written=false`,
  `config_written=false`, `raw_prompt_recorded=false`,
  `raw_route_id_recorded=false`, `raw_backend_details_exposed=false`,
  `secret_value_exposed=false`, `product_ready=false`, and
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
  provider responses, raw route ids, backend URLs, provider headers, API keys,
  and secret values were not recorded

## Notes

- blockers encountered: the previous boundary builder accepted test-shaped
  submit-boundary evidence without producer provenance; the bounded CLI runner
  also had an ambiguous temp-write surface until it was explicitly labeled as
  owned temp scratch, not effective runtime/config truth
- residual risk: claim digests are packet-integrity guards, not external
  cryptographic provenance signatures; a fully self-consistent forged packet is
  outside this contour's trust boundary
- resume from here: CLOSED
