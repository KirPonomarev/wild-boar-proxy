<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Assistant Completion Exact Token Proof v2 Closeout

## Goal

Prove or safely reject native Custom Codex assistant completion as a bounded runtime
fact: prompt accepted, assistant activity observed, assistant activity ended, a
post-completion scan performed, and the expected standalone response token observed
as a request-bound response rather than prompt echo.

## Result

- status: completed with fail-closed runtime verdict
- final verdict: positive product proof was not earned; the runtime proof layer now
  distinguishes activity, completion, prompt echo, and exact standalone response
- closure state: CLOSED

## Contour Capsule

- goal: strengthen Assistant Completion / Exact Token Proof v2 and rerun live
  Custom Codex evidence without treating prompt submit, activity, or prompt echo as
  a visible response proof
- branch: `codex/stabilize-runtime-core`
- head: `189ea002c176158a640439b734e1b285870c918d` before this closeout commit
- touched files: `wild_boar_proxy/native_window_probe.py`,
  `wild_boar_proxy/custom_codex_native_ui_observer_proof.py`,
  `wild_boar_proxy/custom_codex_ui_visibility_proof.py`,
  `wild_boar_proxy/cli.py`, `tests/test_native_launch_dispatch.py`,
  `tests/test_custom_codex_ui_visibility_proof.py`, `tests/test_cli.py`,
  `audit_results/assistant_completion_exact_token_proof_v2_closeout_20260622.md`
- tests run: `python3 -m compileall -q wild_boar_proxy/native_window_probe.py wild_boar_proxy/custom_codex_native_ui_observer_proof.py wild_boar_proxy/custom_codex_ui_visibility_proof.py wild_boar_proxy/cli.py tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py tests/test_cli.py`;
  `python3 -m pytest tests/test_native_launch_dispatch.py -k 'cdp_response_observer or native_ui_observer_proof_command or submit_custom_native_window_prompt_passes_same_profile_candidate_pids_to_cdp' -q`;
  `python3 -m pytest tests/test_custom_codex_ui_visibility_proof.py -q`;
  `python3 -m pytest tests/test_cli.py -k 'native_ui_observer_proof or command_effect' -q`;
  `python3 -m pytest tests/test_native_launch_dispatch.py tests/test_custom_codex_ui_visibility_proof.py tests/test_cli.py -q`;
  `git diff --check`
- blocked risks: live Custom Codex response remained prompt echo only; no exact
  standalone response token was proven
- closure state: CLOSED

## Verification

- tests: 607 Python tests and 121 subtests passed across
  `tests/test_native_launch_dispatch.py`, `tests/test_custom_codex_ui_visibility_proof.py`,
  and `tests/test_cli.py`
- build: targeted `compileall` passed for touched Python modules and tests
- manual: independent auditor checked fresh diff and live evidence; no false-green,
  raw prompt, raw DOM, raw response, or secret exposure was found
- live verification: `/private/tmp/wbp-assistant-completion-proof-20260621T215452Z`
  recorded `prompt_submitted=true`, `native_prompt_turn_accepted=true`,
  `assistant_turn_activity_observed=true`, `assistant_turn_completed_observed=true`,
  `assistant_turn_activity_ended_observed=true`,
  `assistant_turn_post_completion_scan_performed=true`,
  `assistant_turn_machine_error_code=CUSTOM_NATIVE_ASSISTANT_TURN_PROMPT_ECHO_ONLY`,
  `custom_response_exact_token_observed=false`,
  `native_ui_observer_packet_proven=false`, and final
  `custom_codex_ui_visibility_proven=false`

## Artifacts

- spec: current task thread and repository canon
- packet: `/private/tmp/wbp-assistant-completion-proof-20260621T215452Z/native-ui-observer.packet.json`
- packet: `/private/tmp/wbp-assistant-completion-proof-20260621T215452Z/custom-codex-ui-visibility-proof.stdout.json`
- packet: `/private/tmp/wbp-assistant-completion-proof-20260621T215452Z/visible-source-binding-proof.packet.json`
- report: independent auditor result in the current task thread

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no staged contour work outside runtime proof, CLI
  plumbing, proof verifier, tests, and this closeout; existing dirty UI files were
  left unstaged
- private-data risk reviewed: prompt text, raw DOM, raw AX tree, provider response
  text, provider preview, backend details, and secrets all remained unrecorded in
  live proof packets

## Notes

- blockers encountered: the live Custom Codex UI returned only prompt echo evidence
  for the expected token; bounded observer and verifier rejected it
- resume from here: CLOSED
