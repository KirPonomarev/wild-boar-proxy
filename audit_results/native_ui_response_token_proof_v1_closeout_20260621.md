<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native UI Response Token Proof v1 Closeout

## Goal

Truthfully resolve whether the real WBP Custom Codex native UI can show a
handoff-bound exact response token after a native prompt submit, without using
local imitation, fallback, raw DOM capture, raw prompt storage, or product-ready
claims.

## Result

- status: diagnostic closed
- final verdict: `custom_codex_ui_visibility_proven=false`
- closure state: CLOSED

The contour repaired a false-green boundary in native prompt submission:
`prompt_submitted=true` now requires prompt acceptance by the Codex working flow,
not just a clicked button or dispatched key event.

The live rerun proved prompt insertion and prompt acceptance by the real WBP
Custom Codex native UI. It did not prove an exact standalone visible response
token. The only handoff-bound token candidate observed in the UI was classified
as prompt suffix echo, not as assistant response.

## Contour Capsule

- goal: native UI response token proof v1
- branch: `codex/stabilize-runtime-core`
- head: `9eb2b257db3f78c8a6eb99da3aa4a6ea8b0b9136` at proof execution
- touched files: `wild_boar_proxy/native_window_probe.py`, `wild_boar_proxy/custom_codex_ui_visibility_proof.py`, `tests/test_native_launch_dispatch.py`, `tests/test_custom_codex_ui_visibility_proof.py`, `audit_results/native_ui_response_token_proof_v1_closeout_20260621.md`
- tests run: `python3 -m pytest tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py -q`; `python3 -m compileall -q wild_boar_proxy/native_window_probe.py wild_boar_proxy/custom_codex_ui_visibility_proof.py`
- blocked risks: button-click false-green, prompt-echo false-green, product-ready overclaim, fallback/local-imitation overclaim, raw prompt or raw DOM exposure
- closure state: CLOSED

## Verification

- tests:
  - targeted submit/observer suite: 6 passed, 80 deselected
  - UI visibility proof suite: 16 passed
  - combined relevant suite: 102 passed
- build:
  - `python3 -m compileall -q wild_boar_proxy/native_window_probe.py wild_boar_proxy/custom_codex_ui_visibility_proof.py`
- manual:
  - no operator UI click was required for the final live rerun
- live verification:
  - proof dir: `/private/tmp/wbp-native-ui-response-token-proof-20260621T210844Z`
  - native observer packet: `status=ok`, `machine_error_code=OK`
  - final UI visibility packet: `status=error`, `machine_error_code=WBP_CUSTOM_CODEX_UI_VISIBILITY_NATIVE_UI_NOT_OBSERVED`

## Artifacts

- native observer stdout packet:
  - `/private/tmp/wbp-native-ui-response-token-proof-20260621T210844Z/native-ui-observer.stdout.json`
  - sha256: `eacd3814c3194ab5f54071c557ee656673912af494b2da1cfed84ab7dd45bc66`
- native observer file-backed packet:
  - `/private/tmp/wbp-native-ui-response-token-proof-20260621T210844Z/native-ui-observer/native-ui-observer.packet.json`
  - sha256: `b7c6a852fd5a29579f557002229e3eec07383d8d99154e90c7f41bf69dba8599`
- final UI visibility packet:
  - `/private/tmp/wbp-native-ui-response-token-proof-20260621T210844Z/custom-codex-ui-visibility-proof.packet.json`
  - sha256: `9501e266f6458086ecf868099d7f2d25f1228718dcdff422aa9f27593b6af112`

## Key Packet Facts

- `native_prompt_submitted=true`
- `native_prompt_turn_accepted=true`
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
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing UI edits were left unstaged and untouched
- private-data risk reviewed: yes
- raw prompt stored in closeout: no
- raw expected visible text stored in closeout: no
- raw DOM or AX tree stored in closeout: no
- raw backend/provider response stored in closeout: no

## Notes

- blockers encountered: the native UI accepted the prompt, but the observer saw
  only a prompt suffix echo token candidate and no exact standalone assistant
  response token.
- resume from here: CLOSED
