<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Interactive Codex Working-Flow Delivery v1 Closeout

## Goal

Prove that an already proven interactive Custom Codex hook/API/handoff packet can be joined to a file-backed Codex working-flow transcript, without claiming Custom Codex UI visibility, native free-chat routing, or product readiness.

## Result

- status: closed
- final verdict: `codex_working_flow_delivery_proven=true` is now available only through a digest-bound join of interactive proof, source proof, Codex JSONL, working-flow proof, and strict proof seal input hashes.
- closure state: CLOSED

## Contour Capsule

- goal: implement and verify `codex-runner interactive-working-flow-delivery` as a strict file-backed join from interactive Custom Codex proof to Codex working-flow delivery proof.
- branch: `codex/stabilize-runtime-core`
- head: `0acc4c8c2efc2f3e9376e19a7ab4749fd79e14ae`
- touched files: `wild_boar_proxy/interactive_codex_working_flow_delivery.py`, `wild_boar_proxy/cli.py`, `tests/test_interactive_codex_working_flow_delivery.py`, `audit_results/interactive_codex_working_flow_delivery_v1_closeout_2026-06-17.md`
- tests run: `python3 -m pytest tests/test_interactive_codex_working_flow_delivery.py -q`; `python3 -m pytest tests/test_interactive_custom_codex_proof.py tests/test_codex_working_flow_delivery_proof.py tests/test_interactive_codex_working_flow_delivery.py tests/test_proof_seal.py -q`; `python3 -m pytest tests/test_cli.py -q -k 'interactive or working_flow_delivery or working-flow-delivery'`; `make test-core`; `python3 -m pytest tests/test_cli.py tests/test_interactive_codex_working_flow_delivery.py -q`; `git diff --check`
- blocked risks: forged self-consistent proof seal input hashes, source proof digest mismatch, missing assistant continuation, local Codex subagent used as DIP, UI/product/native-router overclaim
- closure state: CLOSED

## Verification

- tests: `tests/test_interactive_codex_working_flow_delivery.py` passed 6 tests, including positive join, forged seal input hash mismatch, source digest mismatch, missing assistant continuation, local subagent block, and CLI packet emission.
- build: `make test-core` passed with `418 passed, 120 subtests passed`.
- manual: `git diff --check` passed.
- live verification: `/Volumes/Work/wbp-proof-homes/interactive-working-flow-delivery-live-20260617T-proof2/interactive-working-flow-delivery-proof.packet.json` returned `status=ok`, `machine_error_code=OK`, `codex_working_flow_delivery_proven=true`, `codex_exec_working_flow_delivery_proven=true`, `assistant_continuation_bound=true`, `working_flow_seal_input_hashes_bound=true`, `custom_codex_ui_visibility_proven=false`, `native_free_chat_router_proven=false`, `product_ready=false`.

## Artifacts

- spec: current task thread and canon; no repo-resident forward plan added.
- packet: `/Volumes/Work/wbp-proof-homes/interactive-working-flow-delivery-live-20260617T-proof2/interactive-working-flow-delivery-proof.packet.json`
- report: this closeout file

## Git

- branch: `codex/stabilize-runtime-core`
- commit: to be created after closeout checks
- pushed: to be pushed after commit

## Scope Check

- unrelated work mixed in: no. Pre-existing dirty files `tests/test_web_design_ui.py` and `wild_boar_proxy/web_design_ui/scripts/overview.js` were left untouched and unstaged.
- private-data risk reviewed: yes. Packets record digests and booleans, not raw prompt text, raw route ids, provider response text, backend details, or secrets.

## Notes

- blockers encountered: first live replay over old `codex-exec-ledger.stdout.jsonl` correctly failed because it did not contain assistant continuation or a recognized delivery surface. A second live run initially failed with `route_not_found` until `WBP_EXTERNAL_MODELS_DIR=$HOME/.wild-boar-proxy/external-models` was declared; the final run then passed.
- resume from here: CLOSED
