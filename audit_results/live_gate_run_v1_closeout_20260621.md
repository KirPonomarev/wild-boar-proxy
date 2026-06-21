<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Live Gate Run v1 Closeout

## Goal

Prove the completed Custom Codex proof chain with a fresh file-backed runtime run:
Custom Codex prompt submit, trusted UserPromptSubmit hook ledger, live API lane,
approved handoff, Codex working-flow delivery, and final live manual gate.

## Result

- status: ok
- final verdict: CLOSED with positive `wbp_live_manual_gate_proof`
- closure state: CLOSED

## Contour Capsule

- goal: prove Live Gate Run v1 from Custom Codex prompt submit to live manual gate packet
- branch: codex/stabilize-runtime-core
- head: 5c2d37f785c070ea67072c245d525343e17c8b4c at proof execution
- touched files: audit_results/live_gate_run_v1_closeout_20260621.md
- tests run: 20 targeted proof tests OK; make test-core OK; acceptance packet check OK; git diff --check OK
- blocked risks: stale/orphan proof artifacts, product/UI/native-router overclaim, fallback/local imitation, raw prompt/jsonl/provider leakage
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_live_manual_gate_proof tests.test_interactive_custom_codex_proof tests.test_interactive_codex_working_flow_delivery` -> 20 tests OK
- build: `make test-core` -> 418 passed, 120 subtests passed
- manual: Custom Codex profile exec wrote a fresh trusted UserPromptSubmit hook ledger after preflight cleared the previous ledger
- live verification: `live-manual-gate-proof.packet.json` status `ok`, machine error `OK`, blocking reasons `[]`

## Artifacts

- spec: current thread contour text, no repo-resident forward plan
- packet: `/private/tmp/wbp-live-gate-run-20260621T203556Z/live-manual-gate-proof.packet.json`
- report: this closeout file

Proof artifact hashes:

- `interactive-preflight.packet.json`: `7af1b6119f993562afcd199012905595661f35a9fc59a6c838eac482226212bc`
- `interactive-custom-codex-proof.packet.json`: `0150045454bf6cda375cad1948649130c1a1a72d1430e6880d2cb9e1de70c131`
- `interactive-user-prompt-submit-proof.packet.json`: `21a4011a711ad26feed799d7286a8c39db0072b9096a9a07c26c4a9773880c8c`
- `interactive-working-flow-delivery-proof.packet.json`: `7c2358144b831d5ed2b11d7a32134142adcd8ab2bebdf6846b17012745872949`
- `working-flow-delivery-proof.packet.json`: `ba2d5a796de88abaaa19924e77c963d534b06f0bde7c8378d48acf8c5afdc3d0`
- `working-flow-delivery-proof.seal.json`: `553f8ef6d89f9bd9194821fa506558f4a3d6ce1da07479295857bbc55060259a`
- `working-flow-delivery-proof.seal-verify.packet.json`: `23a7a7c2ed8592a6a1b69b0c79a5e05548f9d875f04d54fc75e0a9b5155213ca`
- `live-manual-gate-proof.packet.json`: `f5024ba320a4f24fb1e321564e98c14f1b4c9bf0a465e03f682212de49cc475f`
- `codex-natural-submit.jsonl`: `26efd7dba89e44107d7e06955a7f5b67e5965b2e555350a21f3eef4a6b469cac`
- `codex-mcp-working-flow.jsonl`: `181ceb4c2e53a38ccf37b676076a1ff13b1e05eadaf15d65aa130e2df08ce888`

Final packet confirmed:

- `live_manual_gate_proven=true`
- `trusted_user_prompt_submit_hook_ran=true`
- `real_custom_codex_prompt_submit_proven=true`
- `api_lane_called=true`
- `codex_working_flow_delivery_proven=true`
- `sealed_working_flow_file_sha256_bound=true`
- `working_flow_seal_file_verified=true`
- `fallback_used=false`
- `local_imitation_used=false`
- `native_codex_subagent_used_as_dip=false`
- `product_ready=false`
- `custom_codex_ui_visibility_proven=false`
- `native_free_chat_router_proven=false`
- `raw_prompt_recorded=false`
- `raw_jsonl_recorded=false`
- `secret_value_exposed=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: 5c2d37f785c070ea67072c245d525343e17c8b4c was the implementation head used for the proof run
- pushed: implementation head already pushed before this closeout

## Scope Check

- unrelated work mixed in: no; pre-existing unstaged UI files were not staged or modified by this contour
- private-data risk reviewed: yes; closeout records packet hashes and boolean proof results only, not raw prompt text, raw JSONL content, provider payloads, auth material, or backend secrets

## Notes

- blockers encountered: default readiness probe without explicit WBP env looked at the wrong profile; rerunning with explicit WBP env resolved the false diagnostic
- resume from here: CLOSED
