<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CUSTOM_CODEX_CHATGPT_AND_API_SIMULTANEOUS_SESSION_R1 Closeout

## Goal

Reprove that one Custom Codex environment/session truth can hold and call both
the ChatGPT/Codex lane and one API/WBP route-backed lane without silent source
collapse, false same-session claims, or fake upgrade into concurrent execution,
provider-family compatibility, persistence, or final workflow proof.

## Result

- status: completed
- final verdict: same-session dual-lane callability remains packet-backed on current code and current focused probes; contour closes with explicit limits rather than concurrency, persistence, or item-7/item-12 overclaim
- closure state: CLOSED

## Contour Capsule

- goal: reprove same-session dual-lane environment identity, lane-specific callability, provenance separation, and substitution boundaries on the current branch after native lane recovery
- branch: codex/external-agent-lab-isolated
- head: `a38b81e7`
- touched files:
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/chatgpt_lane_runtime_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/api_lane_runtime_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/simultaneous_session_runtime_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/dual_lane_source_provenance_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/slot_dispatch_separation_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/fallback_and_substitution_boundary_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/simultaneous_session_non_claims_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/simultaneous_session_gap_matrix.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/false_green_boundary_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/independent_audit_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/probe_session_root/ccs-4c4860dcbbd84542a726/session.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/probe_session_root/ccs-4c4860dcbbd84542a726/ledger.jsonl`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/probe_session_root/ccs-4c4860dcbbd84542a726/transcript.jsonl`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest -q tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`
  - `python3 -m pytest -q tests/test_codex_custom_sessions.py -k "slot or route_provenance or SLOT_ID_NOT_SERVER_ISSUED or coding_agent_model_slot or current_execution_slot_id"`
  - `'/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3' -m unittest tests.test_web_design_live_server.WebDesignCodexCustomDualLaneSelectorEndpointTests tests.test_web_design_live_server.WebDesignCodexCustomSessionEndpointTests.test_codex_custom_same_session_prompt_can_exercise_chatgpt_and_api_lanes`
  - `python3 -m py_compile tools/custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py wild_boar_proxy/codex_custom_sessions.py wild_boar_proxy/codex_account_selection.py wild_boar_proxy/codex_model_registry.py wild_boar_proxy/operator_surface.py`
  - `python3 tools/custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29`
- blocked risks:
  - concurrent execution remains unobserved and non-claim
  - only ChatGPT lane plus one API coding-agent lane are runtime-proven here
  - persistence/relaunch continuity remains separate and unproven in this contour
  - item 7 semantics and item 12 full workflow remain gated
- closure state: CLOSED

## Verification

- tests:
  - `2 passed` in `tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`
  - `10 passed` in the focused `tests/test_codex_custom_sessions.py` slice for slot/runtime/provenance behavior
  - `4 passed` in the focused bundled-runtime `tests.test_web_design_live_server` HTTP slice for dual-lane selector and same-session prompt dispatch
- build:
  - `py_compile` passed for the contour-local probe and current session/selection/runtime modules
- manual:
  - contour-local probe wrote `10/10` JSON packets with parseable bodies under a fresh 2026-05-29 evidence directory
- live verification:
  - current native prerequisite remained healthy before contour execution: stable native lane had already been reproved with `healthcheck --json = OK`, `status --json = OK`, and direct native `/v1/responses = 200`
  - the focused live-server slice exercised `/api/codex/custom/sessions` and `/api/codex/custom/sessions/{id}/prompt` with one session containing both `primary_model_slot = gpt-5.3-codex` and `coding_agent_model_slot = wbp-deepseek-v3`
  - the same session then served one ChatGPT-lane prompt with `selected_source_provenance = backend_proven` and `configured_provider = cliproxy`
  - the same session then served one API-lane prompt with `selected_source_provenance = route_proven` and `configured_provider = external_route`
  - runner payload truth preserved explicit slot dispatch: first call stayed on `primary_model_slot`, second call stayed on `coding_agent_model_slot`
  - no browser-authored backend authority, no silent fallback, and no lane-source collapse were observed

## Artifacts

- spec: thread-only contour plan for `CUSTOM_CODEX_CHATGPT_AND_API_SIMULTANEOUS_SESSION_R1`
- packet:
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/simultaneous_session_runtime_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/dual_lane_source_provenance_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/slot_dispatch_separation_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/fallback_and_substitution_boundary_packet.json`
  - `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-29/independent_audit_packet.json`
- report:
  - one current session id (`ccs-4c4860dcbbd84542a726`) carried both lane calls
  - provenance stayed lane-specific: ChatGPT lane remained `backend_proven`/`cliproxy`, API lane remained `route_proven`/`external_route`
  - same-session callability is current truth; concurrent execution, provider-family compatibility, and persistence remain explicit non-claims

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no; unrelated dirty files and historical artifact churn outside this contour were left untouched
- private-data risk reviewed: yes; current packets keep prompts bounded/redacted, preserve only lane/provenance/session truth, and admit no raw browser authority over backend ids, routes, paths, or secrets

## Notes

- blockers encountered:
  - a first attempt to run the focused `tests/test_web_design_live_server.py` slice under system `python3` failed because that interpreter lacked `_tkinter`; the contour switched to the bundled runtime python for the affected HTTP-path unittests
  - current contour evidence intentionally does not upgrade same-session callability into concurrent execution, persistence, item-7 semantics, or item-12 workflow closure
  - no new runtime repair was required in this contour; the work was a fresh current-code reproof after the native-lane recovery stream
- resume from here: CLOSED
