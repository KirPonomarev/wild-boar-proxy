<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Router Hook Control Boundary Evidence Admission Closeout

## Goal

Create a production packet builder for WBP-owned router hook control-boundary
evidence and make source-event admission reject manually shaped boundary
dictionaries.

## Result

- status: completed
- final verdict: `wbp_router_hook_control_boundary` now derives control-boundary
  claims from bounded WBP evidence only; `wbp_router_hook_source_event` now
  requires the produced boundary packet shape, producer marker, final status,
  no-write proof, prompt/run digest binding, and matching claim digest
- closure state: CLOSED

## Contour Capsule

- goal: close the false-green gap where an arbitrary control-boundary mapping
  could claim WBP ownership and router enforcement
- branch: codex/stabilize-runtime-core
- head: ea8f02178dfc0ab7b0e979e89921ed044b531a33 pre-closeout base; closure
  commit includes this evidence and scoped MCP/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py;
  audit_results/router_hook_control_boundary_evidence_admission_closeout_2026-06-16.md
- tests run: Python compile passed; MCP delegate unittest and pytest passed;
  diff whitespace and line-length checks passed; adversarial packet smoke
  passed; `make test-core` passed; independent read-only audit passed; closeout
  resilience check passed
- blocked risks: manual control-boundary false green; synthetic boundary false
  green; post-factum Codex JSONL observer promoted to WBP control boundary;
  producer marker drift; final status drift; claim digest tamper; changed-files
  tamper; write side effects; prompt/browser supplied hook authority; raw
  prompt, raw route id, backend detail, or secret exposure; product-ready or
  native-free-chat claims from boundary/source packets
- closure state: CLOSED

## Verification

- tests: `python3 -m py_compile wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- tests: `python3 -m unittest tests.test_mcp_delegate` -> 67 tests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS="-p no:cacheprovider"
  python3 -m pytest -q tests/test_mcp_delegate.py` -> 67 passed, 32 subtests
  passed
- tests: `make test-core` -> 418 passed, 120 subtests passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py
  tests/test_mcp_delegate.py` -> passed
- build: line-length scan for `wild_boar_proxy/mcp_delegate.py` and
  `tests/test_mcp_delegate.py` -> passed
- manual: adversarial packet smoke returned valid boundary/source `PASS`,
  product/native claim absence `PASS`, manual boundary rejection `PASS`,
  post-factum boundary/source rejection `PASS`, and changed-files tamper
  rejection `PASS`
- manual: independent auditors Avicenna and Schrodinger confirmed the builder
  accepts bounded WBP-owned pre-Codex evidence, rejects post-factum JSONL-only
  boundary claims, rejects manual boundary dictionaries, blocks prompt/browser
  authority, write side effects, raw prompt/route/backend/secret exposure, and
  does not mix UI, live-provider, Codex-patch, or runtime-write layers
- live verification: no external provider network call was executed in this
  contour

## Artifacts

- spec: current task-thread contour definition
- packet: `wbp_router_hook_control_boundary`
- packet: `wbp_router_hook_source_event`
- report: success packets prove `control_boundary_status=ok`,
  `control_boundary_wbp_owned=true`, `control_boundary_observed_prompt=true`,
  `control_boundary_prompt_digest_bound=true`,
  `control_boundary_run_digest_present=true`,
  `control_boundary_pre_codex_decision=true`,
  `control_boundary_post_factum_only=false`,
  `control_boundary_can_enforce_router=true`,
  `control_boundary_can_route_delegate_to_dip=true`,
  `control_boundary_claim_digest_matched=true`,
  `manual_boundary_evidence_used=false`, `synthetic_boundary_evidence_used=false`,
  `prompt_supplied_hook_flags=false`, `browser_supplied_hook_flags=false`,
  `product_ready=false`, and `native_free_chat_router_proven=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped MCP/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged
  and untouched
- private-data risk reviewed: auth files, raw prompts, raw transcripts, raw
  provider responses, raw route ids, backend URLs, provider headers, API keys,
  and secret values were not recorded

## Notes

- blockers encountered: the previous source-event consumer could accept a
  manually shaped control-boundary dict without proving producer provenance or a
  bound control-boundary claim digest
- residual risk: claim digest is a packet-integrity guard, not an external
  cryptographic process attestation; a fully self-consistent forged packet is
  outside this contour's trust boundary
- resume from here: CLOSED
