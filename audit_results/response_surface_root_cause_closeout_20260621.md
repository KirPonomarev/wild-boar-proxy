<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Response Surface Root Cause Closeout

## Goal

Diagnose and harden the real Custom Codex native response observer after the
previous UI-visibility gate proved prompt insertion and turn completion, but did
not prove an exact visible response token bound to the request.

## Result

- status: diagnostic closed
- final verdict: Custom Codex prompt acceptance and assistant turn completion are proven, while the expected token remains prompt-echo-only and absent from response-like surfaces.
- closure state: CLOSED

## Contour Capsule

- goal: response surface root-cause proof for Custom Codex native UI observer
- branch: codex/stabilize-runtime-core
- head: e7c6bf757959543b6b9e5f5437976add4015460a
- touched files: wild_boar_proxy/native_window_probe.py; tests/test_native_launch_dispatch.py; audit_results/response_surface_root_cause_closeout_20260621.md
- tests run: python3 -m compileall -q wild_boar_proxy/native_window_probe.py tests/test_native_launch_dispatch.py; python3 -m pytest tests/test_native_launch_dispatch.py -k 'cdp_response_observer or cdp_prompt_submit_inserts_text_accepts_turn_and_observes_exact_response' -q; python3 -m pytest tests/test_native_launch_dispatch.py -k 'cdp_response_observer or native_ui_observer_proof or cdp_prompt_submit_inserts_text_accepts_turn_and_observes_exact_response' -q; python3 -m pytest tests/test_custom_codex_ui_visibility_proof.py -q; python3 -m pytest -q tests/test_native_launch_dispatch.py -k 'bounded_hashed_candidate_map or reports_completion_without_exact_even_with_prompt_echo or prompt_echo_only or greenwash_prompt_submit_only or greenwash_candidate_map_only'; python3 -m pytest tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py -q; python3 -m pytest tests/test_cli.py -k 'native_ui_observer_proof or custom_codex_ui_visibility or command_effect' -q; git diff --check
- blocked risks: false positive UI-visibility proof, product-ready overclaim, prompt echo mistaken for assistant response, raw prompt or DOM leakage through diagnostics, stale async CDP promise evaluation
- closure state: CLOSED

## Verification

- tests:
  - focused response observer slice: 9 passed, 84 deselected
  - response observer plus native UI proof slice: 11 passed, 82 deselected
  - Custom Codex UI visibility proof suite: 17 passed
  - auditor-recommended false-green guard slice: 4 passed, 90 deselected
  - native launch dispatch plus UI visibility proof suites: 111 passed
  - CLI filtered proof command slice: 1 passed, 497 deselected
- build: compileall passed for wild_boar_proxy/native_window_probe.py and tests/test_native_launch_dispatch.py
- manual: live WBP Clean native app proof packet inspected from pid-bound CDP observer output
- live verification:
  - proof root: /private/tmp/wbp-response-surface-root-cause-20260621T222524Z
  - native prompt accepted: true
  - assistant turn completed: true
  - candidate map available: true
  - candidate map count: 13
  - response surface candidate count: 187
  - exact token candidate count: 0
  - response-like candidate count: 0
  - prompt echo candidate count: 1
  - prompt suffix echo candidate count: 1
  - assistant turn machine error code: CUSTOM_NATIVE_ASSISTANT_TURN_COMPLETED_WITHOUT_EXACT_TOKEN
  - custom_codex_ui_visibility_proven: false
  - product_ready: false

## Artifacts

- spec: current task thread and repository canon
- packet: /private/tmp/wbp-response-surface-root-cause-20260621T222524Z/native-ui-observer.packet.json
- report:
  - native observer packet sha256: c5f13b662ec315a3d12743b387a028e7922f7dc682fd570c0c741677b57b92fd
  - native observer stdout sha256: 32149f943f9eb7236624799933d4e49adc9c35a9d03086d5941575de88caa0da

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left outside this contour
- private-data risk reviewed: yes; the bounded candidate map stores counts, booleans, sanitized labels, element bounds, and SHA-256 hashes, not raw prompt text, raw DOM, raw response text, route ids, provider responses, backend details, or secrets

## Notes

- blockers encountered: the live response observer initially failed to scan because async CDP evaluation was not awaited in prompt acceptance and the response observer expression needed an async IIFE for candidate hashing.
- resume from here: CLOSED
