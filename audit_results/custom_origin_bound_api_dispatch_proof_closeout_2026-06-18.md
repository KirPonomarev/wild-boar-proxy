<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom-Origin-Bound API Dispatch Proof Closeout

## Goal

Prove the narrow runtime chain:

`real Custom Codex UI submit -> UserPromptSubmit hook -> fresh file-backed ledger -> Custom UI origin admission -> runtime alias/context allowlist -> controlled API-lane dispatch`

This contour explicitly did not prove live external provider response, handoff
delivery, Custom Codex UI visibility of an answer, native free-chat router
product readiness, or product readiness.

## Result

- status: ok
- final verdict: closed with Custom-origin-bound controlled API dispatch proof
- closure state: CLOSED

## Contour Capsule

- goal: bind a fresh real Custom Codex UI submit ledger to route-bound controlled API dispatch without claiming product readiness
- branch: codex/stabilize-runtime-core
- head: 620ee1aa before closeout commit
- touched files: wild_boar_proxy/custom_origin_bound_api_dispatch_proof.py; wild_boar_proxy/custom_ui_origin_admission.py; wild_boar_proxy/cli.py; tests/test_custom_origin_bound_api_dispatch_proof.py; audit_results/custom_origin_bound_api_dispatch_proof_closeout_2026-06-18.md
- tests run: python3 -m pytest tests/test_custom_origin_bound_api_dispatch_proof.py; python3 -m pytest tests/test_custom_ui_origin_admission.py tests/test_real_ledger_bound_api_dispatch_proof.py tests/test_controlled_api_dispatch.py; python3 -m pytest tests/test_real_custom_app_submit_ledger_proof.py tests/test_real_user_prompt_submit_ledger_proof.py tests/test_user_prompt_submit_hook_producer.py; combined focused suite; make test-core; python3 -m pytest tests/test_cli.py; live Custom Codex CDP submit plus custom-origin-bound dispatch proof; command-packet semantic and prompt-secret scan; independent read-only audit
- blocked risks: live external provider response, handoff delivery, Custom Codex UI answer visibility, native free-chat router product readiness, product readiness, fallback, local imitation, native Codex subagent-as-DIP, raw prompt exposure, raw route id exposure, raw backend/provider detail exposure, and secret exposure remain false or explicitly blocked
- closure state: CLOSED

## Verification

- focused new suite: 7 passed
- adjacent proof suites: 60 passed
- combined focused suite: 67 passed
- make test-core: 418 passed, 120 subtests passed
- full CLI suite: 496 passed
- packet semantic scan: no violations
- prompt secret scan: false
- independent audit: no blocking findings

## Live Proof

- live Custom Codex submit packet:
  - status=ok
  - machine_error_code=OK
  - cdp_port_owner_bound_to_custom_profile=true
  - input_text_insert_succeeded=true
  - prompt_submitted=true
  - submit_mechanism=cdp_keyboard_event_enter
- ledger freshness:
  - ledger mtime before submit: 1781748680217093486
  - ledger mtime after submit: 1781749601829809153
  - prompt digest: 87f68a76c5abbe22548ee892812553ce6a4658206166e0914053a11d8f1f5c2c
- final proof packet:
  - status=ok
  - machine_error_code=OK
  - packet_kind=wbp_custom_origin_bound_api_dispatch_proof
  - launch_surface=launchservices_proof_harness
  - custom_ui_origin_admitted=true
  - fresh_user_prompt_submit_ledger_proven=true
  - custom_origin_bound=true
  - prompt_digest_bound_to_custom_origin_and_dispatch=true
  - alias_context_read=true
  - alias_resolved=true
  - allowed_api_route_ids_enforced=true
  - route_id_allowed=true
  - api_lane_called=true
  - dispatch_attempted=true
  - dispatch_proven=true
  - dispatch_status=proven
  - provider_response_proven=true
  - controlled_provider_response_proven=true
  - live_provider_proven=false
  - custom_codex_ui_visibility_proven=false
  - product_ready=false
  - fallback_used=false
  - local_imitation_used=false
  - native_codex_subagent_used_as_dip=false

## Artifacts

- /tmp/wbp-custom-origin-bound-submit.json
- /tmp/wbp-custom-origin-bound-submit.pretty.json
- /tmp/wbp-custom-origin-bound-dispatch-proof.json
- /tmp/wbp-custom-origin-bound-dispatch-prompt.txt
- /tmp/wbp-custom-origin-bound-dispatch-before-ns.txt
- /tmp/wbp-custom-origin-bound-dispatch-after-ns.txt

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and outside this contour
- private-data risk reviewed: yes; final proof reports raw_prompt_recorded=false, prompt_text_recorded=false, raw_backend_details_exposed=false, secret_value_exposed=false, and no_secret_exposed=true
- product claim reviewed: yes; live_provider_proven=false, custom_codex_ui_visibility_proven=false, handoff_delivered=false, native_free_chat_router_product_ready=false, and product_ready=false

## Notes

- blockers encountered: the first local submit attempt targeted the default inactive CDP port and was discarded; the successful proof used the live pid-bound Custom Codex CDP port. A proof invocation without WBP_PROFILE_DIR was also discarded because the ledger was correctly rejected as not profile-owned for that default environment.
- resume from here: CLOSED
