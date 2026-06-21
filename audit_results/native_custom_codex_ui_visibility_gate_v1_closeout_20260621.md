<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native Custom Codex UI Visibility Gate v1 Closeout

## Goal

Prove or truthfully reject the next post-live-gate claim:

`Custom Codex visible UI response -> handoff-bound WBP proof`

The contour reused the already closed live manual gate chain, added
file-backed visible-source binding, launched a real WBP Custom Codex native app
process, submitted a bounded prompt through the native renderer, and then ran
the final UI visibility verifier.

## Result

- status: diagnostic closed
- final verdict: `custom_codex_ui_visibility_proven=false`
- closure state: CLOSED

The source side passed: the Codex working-flow JSONL was bound to the WBP
handoff digest and the live API lane proof.

The native UI side partly passed: the verifier proved WBP Clean app process
binding, WBP profile binding, visible/frontmost Custom Codex window, input
capable UI, prompt insertion, and prompt submission.

The contour did not produce a positive UI visibility proof because the native
observer did not prove an exact visible response token bound to the request and
handoff digest.

## Contour Capsule

- goal: native Custom Codex UI visibility gate v1
- branch: `codex/stabilize-runtime-core`
- head: `e41b476e2711051a2667b743baeb8097a17131d3` at proof execution
- touched files:
  - `audit_results/native_custom_codex_ui_visibility_gate_v1_closeout_20260621.md`
- tests run:
  - `python3 -m unittest tests.test_custom_codex_ui_visibility_proof tests.test_custom_codex_visible_source_binding_proof tests.test_interactive_codex_working_flow_delivery tests.test_live_manual_gate_proof`
  - `make test-core`
- blocked risks:
  - false UI visibility claim
  - product-ready overclaim
  - native free-chat router overclaim
  - fallback or local imitation claim
  - raw prompt, raw DOM, raw AX tree, raw route id, raw provider response, or secret exposure
- closure state: CLOSED

## Verification

- tests:
  - focused proof suite: 41 tests passed
  - core suite: 418 tests passed and 120 subtests passed
- build: not applicable; no runtime code changed
- manual: WBP Clean native app was launched directly with the WBP profile and pid-bound CDP port
- live verification:
  - proof dir: `/private/tmp/wbp-native-ui-visibility-gate-20260621T204609Z`
  - source binding packet: `status=ok`, `machine_error_code=OK`
  - native observer packet: `status=ok`, `machine_error_code=OK`, native window and prompt submit proven
  - final UI visibility packet: `status=error`, `machine_error_code=WBP_CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED`

## Artifacts

- source binding packet:
  - `/private/tmp/wbp-native-ui-visibility-gate-20260621T204609Z/visible-source-binding-proof.packet.json`
  - sha256: `f1bd5aacaadc394efb2e0c98323871cfbd9c34cafffc3fd170be150ec14f39d0`
- native observer packet:
  - `/private/tmp/wbp-native-ui-visibility-gate-20260621T204609Z/native-ui-observer/native-ui-observer.packet.json`
  - sha256: `3517b777868a68e74ac9966b237d75d70f66f21b7663958fbac804a666c72301`
- scan-after-wait packet:
  - `/private/tmp/wbp-native-ui-visibility-gate-20260621T204609Z/native-ui-observer-scan-after-wait.packet.json`
  - sha256: `0a4f4b60719fcfb17fcbc9daf8576a77b39405df602c62ef70399b42041d5f4f`
- final UI visibility packet:
  - `/private/tmp/wbp-native-ui-visibility-gate-20260621T204609Z/custom-codex-ui-visibility-proof.packet.json`
  - sha256: `ba2c3ba29a36d877ebd66374aa73143a1c47220d3187d6657263fbd3268b9dc3`

## Key Packet Facts

- `visible_source_binding_proven=true`
- `custom_codex_visible_source_binding_proven=true`
- `custom_codex_process_bound=true`
- `custom_codex_window_observed=true`
- `custom_codex_profile_bound=true`
- `custom_codex_native_app_usable=true`
- `input_capable_ui_observed=true`
- `native_prompt_submitted=true`
- `visible_response_observed=false`
- `visible_response_bound_to_handoff=false`
- `visible_response_after_dispatch=false`
- `custom_codex_ui_visibility_proven=false`
- `delivery_counts_as_custom_codex_ui=false`
- `native_free_chat_router_proven=false`
- `product_ready=false`
- `fallback_used=false`
- `local_imitation_used=false`
- `secret_value_exposed=false`
- `raw_prompt_recorded=false`
- `raw_dom_exposed=false`
- `raw_ax_tree_exposed=false`

Primary blocker facts:

- `native_ui_observer_machine_error_code=CUSTOM_NATIVE_FREE_TEXT_OBSERVER_NOT_PROVEN`
- `custom_response_exact_token_candidate_count=0`
- `custom_response_like_candidate_count=0`
- `custom_response_exact_token_not_observed`
- `custom_response_not_bound_to_request`

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout file creation
- pushed: pending at closeout file creation

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- raw prompt stored in closeout: no
- raw expected visible text stored in closeout: no
- raw backend/provider details stored in closeout: no
- pre-existing unstaged UI files touched: no

## Notes

- blockers encountered: the repo launcher fell back to stock Codex because the
  WBP Clean app hash differed from the primary app; a direct WBP Clean launch on
  the pid-bound CDP port produced the required native process and allowed prompt
  submission, but exact response-token visibility was not proven.
- resume from here: CLOSED
