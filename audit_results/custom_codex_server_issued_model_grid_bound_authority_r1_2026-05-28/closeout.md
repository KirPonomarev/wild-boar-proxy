<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Server-Issued Model Grid Bound Authority R1 Closeout

## Goal

Prove that Custom Codex exposes a bounded, quiet, server-issued model catalog where the browser may submit only `model_id`, disabled routes remain visible but not selectable, and no packet or UI surface overclaims provider reachability, route readiness, session launch readiness, auth repair, or UI redesign.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_SERVER_ISSUED_MODEL_GRID_VISIBLE_AND_BOUND
- closure state: CLOSED

## Contour Capsule

- goal: bind Custom Codex model selection to server-owned catalog truth with honest disabled-route visibility and no extra UI noise
- branch: codex/external-agent-lab-isolated
- head: contour evidence commit on codex/external-agent-lab-isolated
- touched files: wild_boar_proxy/codex_model_registry.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; tests/test_codex_model_registry.py; tests/test_wbp_model_catalog_contract.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; tests/test_custom_codex_model_grid_bound_authority_r1_probe.py; tools/custom_codex_server_issued_model_grid_bound_authority_r1_probe.py; tests/test_custom_codex_server_issued_model_grid_bound_authority_r1_probe.py; audit_results/custom_codex_server_issued_model_grid_bound_authority_r1_2026-05-28
- tests run: python3 -m unittest tests.test_codex_model_registry tests.test_wbp_model_catalog_contract tests.test_custom_codex_model_grid_bound_authority_r1_probe tests.test_custom_codex_server_issued_model_grid_bound_authority_r1_probe; python3 -m py_compile wild_boar_proxy/codex_model_registry.py wild_boar_proxy/web_design_live_server.py tools/custom_codex_server_issued_model_grid_bound_authority_r1_probe.py tests/test_codex_model_registry.py tests/test_wbp_model_catalog_contract.py tests/test_custom_codex_model_grid_bound_authority_r1_probe.py tests/test_custom_codex_server_issued_model_grid_bound_authority_r1_probe.py; python3 tools/custom_codex_server_issued_model_grid_bound_authority_r1_probe.py
- blocked risks: disabled-route visibility now stays separate from readiness; session launch readiness, provider reachability, route readiness, auth repair, icon readiness, and UI redesign remain explicit non-claims
- closure state: CLOSED

## Verification

- tests: 41 targeted unit tests passed across registry, contract, bounded-UI, and contour-probe guards
- build: py_compile passed for all touched Python modules in this contour
- manual: generated packets were inspected for disabled-route honesty, model-id-only browser payloads, and server-owned binding boundaries
- live verification: no live provider calls, auth repair, session launch success claim, or UI redesign verification was performed in this contour

## Artifacts

- spec: thread-only contour plan outside the repository
- packet: audit_results/custom_codex_server_issued_model_grid_bound_authority_r1_2026-05-28/model_grid_bound_authority_summary_packet.json
- report: audit_results/custom_codex_server_issued_model_grid_bound_authority_r1_2026-05-28/external_auditor_adjudication_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour evidence commit on codex/external-agent-lab-isolated
- pushed: yes; codex/external-agent-lab-isolated pushed to origin after contour verification

## Scope Check

- unrelated work mixed in: no; pre-existing dirty worktree entries were disclosed through sync_gate_packet.json quarantine and were not treated as this contour's signal
- private-data risk reviewed: yes; packets remained read-only, browser payload checks used synthetic fields only, and no raw secrets or backend internals were exposed

## Notes

- blockers encountered: initial probe overclaimed session-launch success for enabled external routes; the contour was narrowed back to binding authority truth and rerun to green
- resume from here: CLOSED
