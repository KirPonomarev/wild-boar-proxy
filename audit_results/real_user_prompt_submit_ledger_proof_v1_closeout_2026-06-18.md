<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Real UserPromptSubmit Ledger Proof v1 Closeout

## Goal

Prove the narrow ingress contour:

`ordinary Custom Codex prompt submit -> trusted UserPromptSubmit hook -> WBP file-backed ledger`

The contour explicitly did not claim API dispatch, provider response, handoff
delivery, Custom Codex UI visibility, native free-chat router readiness, or
product readiness.

## Result

- status: ok
- final verdict: closed with positive real UserPromptSubmit ledger proof
- closure state: CLOSED

## Contour Capsule

- goal: prove that a trusted Custom Codex UserPromptSubmit hook can create a profile-owned file-backed WBP ledger from stdin transport without dispatch or product overclaim
- branch: codex/stabilize-runtime-core
- head: 8e49580b before commit
- touched files:
  - wild_boar_proxy/user_prompt_submit_hook_producer.py
  - wild_boar_proxy/real_custom_codex_hook_proof.py
  - wild_boar_proxy/real_user_prompt_submit_ledger_proof.py
  - wild_boar_proxy/cli.py
  - tests/test_real_user_prompt_submit_ledger_proof.py
  - audit_results/real_user_prompt_submit_ledger_proof_v1_closeout_2026-06-18.md
- tests run:
  - python3 -m py_compile wild_boar_proxy/user_prompt_submit_hook_producer.py wild_boar_proxy/real_custom_codex_hook_proof.py wild_boar_proxy/real_user_prompt_submit_ledger_proof.py wild_boar_proxy/cli.py
  - python3 -m pytest -q tests/test_real_user_prompt_submit_ledger_proof.py
  - python3 -m pytest -q tests/test_user_prompt_submit_hook_producer.py tests/test_real_custom_codex_hook_proof.py
  - python3 -m pytest -q tests/test_real_user_prompt_submit_ledger_proof.py tests/test_user_prompt_submit_hook_producer.py tests/test_real_custom_codex_hook_proof.py tests/test_cli.py
  - git diff --check
  - make test-core
  - live Custom Codex exec smoke creating a fresh UserPromptSubmit ledger
  - live user-prompt-submit-ledger-proof packet generation
  - redacted ledger summary generation
  - independent read-only audit
- blocked risks: API dispatch, provider response, handoff delivery, Custom Codex UI visibility, native free-chat router proof, native free-chat router product readiness, live provider proof, product readiness, fallback, local imitation, native Codex subagent-as-DIP, raw prompt, raw route id, raw provider response, backend detail, and secret claims remain explicitly false
- closure state: CLOSED

## Verification

- tests:
  - tests/test_real_user_prompt_submit_ledger_proof.py: 7 passed
  - tests/test_user_prompt_submit_hook_producer.py and tests/test_real_custom_codex_hook_proof.py: 26 passed, 26 subtests passed
  - focused CLI/regression stack: 529 passed, 141 subtests passed
  - make test-core: 418 passed, 120 subtests passed
- build: not applicable
- manual: Custom Codex CLI exec was launched with the WBP Custom Codex profile and produced a fresh profile-owned UserPromptSubmit ledger
- live verification:
  - real_user_prompt_submit_ledger_proven=true
  - custom_codex_flow_proven=true
  - custom_codex_origin_proven=true
  - native_router_hook_observed=true
  - user_prompt_submit_hook_observed=true
  - hook_event_transport=stdin
  - hook_prompt_digest_bound=true
  - hook_runtime_context_digest_bound=true
  - codex_hook_trusted_by_profile_state=true
  - api_lane_called=false
  - dispatch_attempted=false
  - dispatch_proven=false
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
- packet: /Volumes/Work/wbp-proof-homes/real-user-prompt-submit-ledger-proof-live-20260617T225057Z/real-user-prompt-submit-ledger-proof.packet.json
- report:
  - /Volumes/Work/wbp-proof-homes/real-user-prompt-submit-ledger-proof-live-20260617T225057Z/user-prompt-submit-readiness.packet.json
  - /Volumes/Work/wbp-proof-homes/real-user-prompt-submit-ledger-proof-live-20260617T225057Z/redacted-ledger-summary.json
  - independent audit result: PASS

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and outside this contour
- private-data risk reviewed: yes; proof packets and the redacted ledger summary contain digests and booleans only, with raw prompt, route id, provider response, backend detail, and secret claims false

## Notes

- blockers encountered: none
- residual risk: this proves trusted profile file-backed hook ledger provenance, not cryptographic event attestation; the proof packet keeps source_file_unforgeable=false and cryptographic_origin_proven=false
- resume from here: CLOSED
