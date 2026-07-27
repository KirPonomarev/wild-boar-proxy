<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Real Ledger-Bound API Dispatch Proof v1 Closeout

## Goal

Prove the narrow dispatch contour:

`real Custom Codex UserPromptSubmit ledger -> prompt digest binding -> alias/context/allowlist -> controlled API lane dispatch -> response digest`

The contour explicitly did not claim handoff delivery, Custom Codex UI
visibility, native free-chat router product readiness, live provider proof, or
product readiness.

## Result

- status: ok
- final verdict: closed with positive real ledger-bound controlled API dispatch proof
- closure state: CLOSED

## Contour Capsule

- goal: prove that a real profile-owned UserPromptSubmit ledger can be bound to the live prompt digest, rechecked against runtime alias context and allowlist, and used for controlled route-bound API dispatch with response digest
- branch: codex/stabilize-runtime-core
- head: e41c4267 before commit
- touched files:
  - wild_boar_proxy/real_ledger_bound_api_dispatch_proof.py
  - wild_boar_proxy/cli.py
  - tests/test_real_ledger_bound_api_dispatch_proof.py
  - audit_results/real_ledger_bound_api_dispatch_proof_v1_closeout_2026-06-18.md
- tests run:
  - python3 -m py_compile wild_boar_proxy/real_ledger_bound_api_dispatch_proof.py wild_boar_proxy/cli.py
  - python3 -m pytest -q tests/test_real_ledger_bound_api_dispatch_proof.py
  - python3 -m pytest -q tests/test_real_ledger_bound_api_dispatch_proof.py tests/test_real_user_prompt_submit_ledger_proof.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_cli.py
  - python3 -m pytest -q tests/test_custom_agent_bindings.py tests/test_custom_codex_ingress_proof.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_controlled_api_dispatch.py tests/test_real_user_prompt_submit_ledger_proof.py tests/test_real_ledger_bound_api_dispatch_proof.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py
  - git diff --check
  - live Custom Codex exec submit smoke with timeout metadata
  - live real-ledger-bound-dispatch-proof packet generation
  - live packet no-leak and command-packet semantics scan
  - make test-core
  - independent read-only audit
- blocked risks: handoff delivery, Custom Codex UI visibility, Codex working-flow delivery, native free-chat router proof, native free-chat router product readiness, live provider proof, product readiness, fallback, local imitation, native Codex subagent-as-DIP, raw prompt, raw route id, raw provider response, backend detail, and secret claims remain explicitly false
- closure state: CLOSED

## Verification

- tests:
  - tests/test_real_ledger_bound_api_dispatch_proof.py: 8 passed, 9 subtests passed
  - focused ledger/router/natural/dispatch/CLI stack: 558 passed, 147 subtests passed
  - adjacent dispatch/delegate stack: 148 passed, 93 subtests passed
  - make test-core: 418 passed, 120 subtests passed
- build: not applicable
- manual: Custom Codex CLI exec was launched with the WBP Custom Codex profile; the exec command timed out after submit, but the profile-owned UserPromptSubmit ledger mtime changed and the ledger-bound proof packet matched the submitted prompt digest
- live verification:
  - real_user_prompt_submit_ledger_proven=true
  - prompt_digest_bound_to_ledger=true
  - prompt_digest_bound_to_dispatch=true
  - ledger_bound_dispatch_admitted=true
  - alias_context_read=true
  - selected_alias=DIP
  - selected_alias_lane=api_route
  - allowed_route_enforced=true
  - allowed_api_route_ids_enforced=true
  - api_lane_called=true
  - api_response_received=true
  - response_digest_bound=true
  - route_bound_dispatch_proven=true
  - real_ledger_bound_api_dispatch_proven=true
  - provider_like_response_only=true
  - live_provider_proven=false
  - handoff_file_written=false
  - handoff_delivered=false
  - custom_codex_ui_visibility_proven=false
  - native_free_chat_router_proven=false
  - product_ready=false
  - fallback_used=false
  - local_imitation_used=false
  - native_codex_subagent_used_as_dip=false
  - raw_prompt_recorded=false
  - raw_route_id_recorded=false
  - raw_provider_response_recorded=false
  - secret_value_exposed=false

## Artifacts

- spec: thread-local contour plan only
- packet: /Volumes/Work/wbp-proof-homes/real-ledger-bound-api-dispatch-proof-live-20260617T231652Z/real-ledger-bound-api-dispatch-proof.packet.json
- report:
  - /Volumes/Work/wbp-proof-homes/real-ledger-bound-api-dispatch-proof-live-20260617T231652Z/real-user-prompt-submit-ledger-proof.packet.json
  - /Volumes/Work/wbp-proof-homes/real-ledger-bound-api-dispatch-proof-live-20260617T231652Z/redacted-ledger-summary.json
  - /Volumes/Work/wbp-proof-homes/real-ledger-bound-api-dispatch-proof-live-20260617T231652Z/custom-codex-exec-submit-metadata.json
  - independent audit result: PASS

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and outside this contour
- private-data risk reviewed: yes; live artifacts were scanned for raw prompt, raw route id, provider details, command packet semantic errors, and secret leaks

## Notes

- blockers encountered: Custom Codex exec timed out after submit; this did not block the contour because the UserPromptSubmit ledger was updated and the digest-bound dispatch packet proved the intended route-bound controlled API dispatch
- residual risk: the wrapper builds controlled dispatch internally and does not accept an external dispatch packet, so a forged nested response digest input is not an available command path in this contour; provider failure is covered fail-closed
- resume from here: CLOSED
