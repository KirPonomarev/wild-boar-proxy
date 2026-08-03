<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B06 Legacy Surface And Evidence-Matrix Regression Closeout

## Goal

Verify that the B02–B05 actor-model changes did not regress the legacy
surfaces: DIP, Agent 2, custom aliases, primary exact replies, direct reply,
auto-route, repo bridge, unknown/ambiguous aliases, legacy runtime context,
and the synthetic/integration/live containment matrix.

## Result

- status: verified
- final verdict: no regression found. All legacy alias/router-hook surfaces
  and the evidence containment matrix pass at the exact B06 head; the full
  local suite (4769 passed) applies to the identical tree
- closure state: CLOSED

## Contour Capsule

- goal: B06 legacy surface and evidence-matrix regression verification
- branch: `codex/b06-legacy-regression`
- head: `53eaf17deb4f9fd3f5afbadc1d3b93274bbec923` (exact B06 head; tree
  identical to the B05 branch head verified by `git diff`)
- touched files: `audit_results/B06_LEGACY_SURFACE_REGRESSION_closeout_2026-08-03.md`
- tests run: legacy/router-hook/bridge regression groups; full local suite
- blocked risks: alias regression (DIP/Agent 2/custom), exact-reply and
  exact-JSON passthrough regression, repo-bridge admission regression,
  fail-closed behavior for unknown/ambiguous aliases, synthetic evidence
  leaking into live claim slots
- closure state: CLOSED

## Verification

- tests:
  - legacy alias/router-hook matrix group -> `271 passed, 26 subtests passed`
    (`test_api_agent_auto_router`, `test_api_agent_direct_reply`,
    `test_custom_agent_bindings`, `test_agent_bindings_kimi_glm`,
    `test_codex_custom_sessions`, `test_false_green_containment`,
    `test_e2e_mode_matrix`, `test_gpt_api_dip_acceptance_gate`,
    `test_gpt_api_dip_product_ready_gate`, `test_evidence_state_machine`,
    `test_transport_normalization`, `test_actor_registry`,
    `test_actor_dispatcher`, `test_read_compatibility_snapshots`,
    `test_fresh_router_ready_proof`)
  - repo-bridge and controlled-dispatch group -> `219 passed, 49 subtests
    passed` (`test_wbp_dip_tool`, `test_controlled_api_dispatch`,
    `test_controlled_ingress_api_dispatch_proof`,
    `test_controlled_dispatch_handoff_proof`, `test_review_bridge_packet_import`,
    `test_review_bridge_apply_admission`, `test_review_bridge_command_bus`,
    `test_review_bridge_live_server`, `test_router_hook_entry`)
  - combined matrix: `490 passed, 75 subtests passed`
  - full local suite on the identical tree -> `4769 passed, 978 subtests
    passed` (solo run; see B05 closeout for the timing-flake evidence)
  - GitHub CI on the merged head: all checks green
- build:
  - n/a (verification contour; no code change)
- manual:
  - CLI smoke for `dispatch resolve`, `actors list`, `actors migrate` covered
    by B02/B05 contours and their suites
- live verification:
  - no live mutation; no provider dispatch

## Artifacts

- spec: plan contract sections 5, 10, 16 (legacy compatibility,
  visible-delivery truth, evidence levels)
- packet: no live packet artifact required
- report: this closeout is the evidence-matrix record

## Git

- branch: `codex/b06-legacy-regression`
- commit: contour commit contains this closeout only
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no credentials touched)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none. The B03 note about legacy evidence-level
  naming (`PHYSICAL_PROVEN` vs canonical `PHYSICAL_VISIBLE_PROVEN`) is
  recorded here as `NOTE_AND_CONTINUE`: the canonical taxonomy is enforced by
  the B03 evidence state machine for all new surfaces; the legacy naming
  remains in historical surfaces and is not a false-green (synthetic/live
  separation verified across the containment matrix)
- resume from here: CLOSED
