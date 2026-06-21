<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Assistant Turn Exact Response Proof v1 Closeout

## Goal

Truthfully resolve whether the real WBP Custom Codex native UI can advance from
native prompt acceptance to an assistant turn with a handoff-bound exact
standalone response token, without using local imitation, fallback, raw DOM
capture, raw prompt storage, or product-ready claims.

## Result

- status: diagnostic closed
- final verdict: `custom_codex_ui_visibility_proven=false`
- closure state: CLOSED

The contour added explicit assistant-turn proof fields to the bounded native
observer and to the final Custom Codex UI visibility verifier. The live run
proved that the real WBP Custom Codex native UI accepted the prompt and that an
assistant turn started. It did not prove an assistant turn completed with the
expected standalone response token.

The final verifier stayed fail-closed: the visible-source packet was valid and
the expected token was bound to both the request id and the handoff digest, but
the native UI packet still had no exact response-token candidate.

## Contour Capsule

- goal: assistant turn exact response proof v1
- branch: `codex/stabilize-runtime-core`
- head: `945744b367e73e69836b548ce8a5712e6cabe8e5` at proof execution
- touched files: `wild_boar_proxy/native_window_probe.py`, `wild_boar_proxy/custom_codex_ui_visibility_proof.py`, `tests/test_native_launch_dispatch.py`, `tests/test_custom_codex_ui_visibility_proof.py`, `audit_results/assistant_turn_exact_response_proof_v1_closeout_20260622.md`
- tests run: `python3 -m pytest tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py -q`; `python3 -m compileall -q wild_boar_proxy/native_window_probe.py wild_boar_proxy/custom_codex_ui_visibility_proof.py tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py`
- blocked risks: assistant-turn false-green, prompt-echo false-green, broad model/runtime blocker false positive, product-ready overclaim, fallback/local-imitation overclaim, raw prompt or raw DOM exposure
- closure state: CLOSED

## Verification

- tests:
  - targeted submit/observer suite: 7 passed, 80 deselected
  - UI visibility proof suite: 16 passed
  - combined relevant suite: 103 passed
- build:
  - `python3 -m compileall -q wild_boar_proxy/native_window_probe.py wild_boar_proxy/custom_codex_ui_visibility_proof.py tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py`
- manual:
  - no operator UI click was required for the final live proof run
- live verification:
  - proof dir: `/private/tmp/wbp-assistant-turn-proof-20260621T213405Z`
  - native observer packet: `status=ok`, `machine_error_code=OK`
  - final UI visibility packet: `status=error`, `machine_error_code=WBP_CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED`

## Artifacts

- native observer stdout packet:
  - `/private/tmp/wbp-assistant-turn-proof-20260621T213405Z/native-ui-observer.stdout.json`
  - sha256: `6fcb56448205f08e99e9b74e2bed34100468f9788ecdc4a9d0ebf5983ac979db`
- native observer file-backed packet:
  - `/private/tmp/wbp-assistant-turn-proof-20260621T213405Z/native-ui-observer/native-ui-observer.packet.json`
  - sha256: `e0a0f39f9ced30a406ad340178cb3d9e0b9bd627d819d827cfe7c0c3fd425296`
- final UI visibility packet:
  - `/private/tmp/wbp-assistant-turn-proof-20260621T213405Z/custom-codex-ui-visibility-proof.packet.json`
  - sha256: `647694ac463ce4a33f0a4d353c0953e7863fbe75e8a897b2220717ca37890310`

## Key Packet Facts

- `visible_source_binding_valid=true`
- `expected_visible_text_contains_handoff_digest=true`
- `expected_visible_text_contains_request_id=true`
- `native_prompt_submitted=true`
- `native_prompt_turn_accepted=true`
- `assistant_turn_probe_attempted=true`
- `assistant_turn_probe_scan_performed=true`
- `assistant_turn_started_observed=true`
- `assistant_turn_completed_observed=false`
- `assistant_turn_failed_observed=false`
- `assistant_turn_machine_error_code=CUSTOM_NATIVE_ASSISTANT_TURN_RESPONSE_NOT_PROVEN`
- `assistant_turn_progress_candidate_count=0`
- `assistant_turn_stop_generating_candidate_count=1`
- `auth_or_backend_blocker_observed=false`
- `model_or_runtime_blocker_observed=false`
- `custom_response_text_read_without_storing=true`
- `custom_response_token_leaf_candidate_count=1`
- `custom_response_prompt_echo_candidate_count=1`
- `custom_response_prompt_suffix_echo_candidate_count=1`
- `custom_response_exact_token_candidate_count=0`
- `custom_response_like_candidate_count=0`
- `custom_response_exact_token_observed=false`
- `visible_response_observed=false`
- `visible_response_bound_to_handoff=false`
- `custom_codex_ui_visibility_proven=false`
- `product_ready=false`
- `fallback_used=false`
- `local_imitation_used=false`
- `raw_prompt_recorded=false`
- `raw_dom_exposed=false`
- `raw_ax_tree_exposed=false`

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push performed after closeout verification

## Scope Check

- unrelated work mixed in: no; pre-existing UI edits were left unstaged and untouched
- private-data risk reviewed: yes
- raw prompt stored in closeout: no
- raw expected visible text stored in closeout: no
- raw DOM or AX tree stored in closeout: no
- raw backend/provider response stored in closeout: no

## Notes

- blockers encountered: the native UI accepted the prompt and showed assistant-turn activity, but the observer saw only a prompt suffix echo token candidate and no exact standalone assistant response token.
- resume from here: CLOSED
