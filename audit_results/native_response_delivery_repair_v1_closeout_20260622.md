<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native Response Delivery Repair v1 Closeout

## Goal

Truthfully prove whether a real WBP Custom Codex native prompt can produce a
handoff-bound visible assistant response in the working Codex flow, without
using local imitation, fallback, prompt echo, raw prompt storage, raw DOM
capture, or product-ready claims.

## Result

- status: positive proof closed
- final verdict: `custom_codex_ui_visibility_proven=true`
- closure state: CLOSED

The contour added a bounded native response prompt matrix and used it to find a
prompt shape that the real Custom Codex UI answered with an exact request-bound
token. That native observer packet was then joined to an existing approved
visible-source handoff proof. The final UI visibility packet proved the response
was observed after dispatch, bound to the handoff, and file-backed by the native
observer packet.

## Contour Capsule

- goal: native response delivery repair v1
- branch: `codex/stabilize-runtime-core`
- head: `f70e760dfe239b78b53ad978bedc81b6a334d14d` before contour commit
- touched files: `wild_boar_proxy/custom_codex_native_response_matrix.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_native_response_matrix.py`, `tests/test_cli.py`, `audit_results/native_response_delivery_repair_v1_closeout_20260622.md`
- tests run: `python3 -m pytest tests/test_custom_codex_native_response_matrix.py tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py -q`; `python3 -m pytest tests/test_custom_codex_native_response_matrix.py tests/test_cli.py -k native_response_matrix -q`; `python3 -m pytest tests/test_custom_codex_approved_visible_source_observation.py tests/test_custom_codex_admission.py -k 'product_ready or custom_codex_ui_visibility_proven or visible_source' -q`; `make test-core`; `python3 -m compileall -q wild_boar_proxy/custom_codex_native_response_matrix.py wild_boar_proxy/cli.py tests/test_custom_codex_native_response_matrix.py tests/test_cli.py`; `git diff --check`
- blocked risks: prompt-echo false-green, candidate-map false-green, native UI visibility overclaim, product-ready overclaim, fallback/local-imitation overclaim, raw prompt/raw expected text/raw DOM exposure
- closure state: CLOSED

## Verification

- tests:
  - native response matrix, launch dispatch, and UI visibility suite: 115 passed
  - native response matrix CLI slice: 5 passed, 498 deselected
  - visible source and admission guard slice: 8 passed, 20 deselected, 12 subtests passed
  - core suite: 418 passed, 120 subtests passed
- build:
  - `python3 -m compileall -q wild_boar_proxy/custom_codex_native_response_matrix.py wild_boar_proxy/cli.py tests/test_custom_codex_native_response_matrix.py tests/test_cli.py`
- manual:
  - no operator UI click was required for the final proof run
- live verification:
  - handoff matrix packet: `status=ok`, `machine_error_code=OK`, `native_response_matrix_proven=true`, `positive_case_count=2`, `case_count=4`
  - selected native observer packet: `status=ok`, `machine_error_code=OK`, `assistant_turn_completed_observed=true`, `custom_response_exact_token_observed=true`
  - final UI visibility packet: `status=ok`, `machine_error_code=OK`, `custom_codex_ui_visibility_proven=true`

## Artifacts

- handoff matrix packet:
  - `/private/tmp/wbp-native-response-matrix-handoff-20260621T224324Z/native-response-matrix.packet.json`
  - sha256: `719ee6e7f87e8cf3bfc384fbacb16e1026f238050a3a1528dbb9bb537a8efc8d`
- selected native observer packet:
  - `/private/tmp/wbp-native-response-matrix-handoff-20260621T224324Z/cases/exact_one_line/native-ui-observer.packet.json`
  - sha256: `3088506815aafeb594450b01d8088e9bf6bfe43fb55b3d5eb06a224a703bfe14`
- final UI visibility packet:
  - `/private/tmp/wbp-native-response-matrix-handoff-20260621T224324Z/ui-visibility-final/custom-codex-ui-visibility-proof.packet.json`
  - sha256: `38f9e53fb5a98ef4caa9cdf12e750bf8f729ac0d4c91361cb3f5ebb7602532da`

## Key Packet Facts

- `visible_response_observed=true`
- `visible_response_bound_to_handoff=true`
- `visible_response_after_dispatch=true`
- `visible_source_binding_valid=true`
- `native_ui_source_allowed=true`
- `native_ui_observer_file_backed=true`
- `native_prompt_submitted=true`
- `assistant_turn_completed_observed=true`
- `assistant_turn_machine_error_code=OK`
- `custom_response_exact_token_observed=true`
- `custom_response_exact_token_candidate_count=2`
- `custom_response_like_candidate_count=2`
- `expected_visible_text_contains_handoff_digest=true`
- `expected_visible_text_contains_request_id=true`
- `native_codex_subagent_absence_proven=true`
- `custom_codex_ui_visibility_proven=true`
- `product_ready=false`
- `do_not_prove_product_ready=true`
- `fallback_used=false`
- `local_imitation_used=false`
- `raw_prompt_recorded=false`
- `raw_dom_exposed=false`
- `raw_provider_response_recorded=false`
- `provider_response_text_recorded=false`
- `provider_response_preview_recorded=false`
- `secret_value_exposed=false`

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing UI worktree edits were left unstaged and untouched
- private-data risk reviewed: yes
- raw prompt stored in closeout: no
- raw expected visible text stored in closeout: no
- raw DOM or AX tree stored in closeout: no
- raw backend/provider response stored in closeout: no
- product shell or UI polish included: no

## Notes

- blockers encountered: initial matrix execution found no live WBP Clean root process, then the app was launched with the WBP profile and the proof rerun; an early handoff-bound matrix used a prefix too short for a digest-bearing source binding, and the matrix helper now preserves digest-sized prefixes.
- resume from here: CLOSED
