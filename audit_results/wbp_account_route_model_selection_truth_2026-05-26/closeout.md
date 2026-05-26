# WBP Account Route Model Selection Truth Closeout

## Goal

Prove that WBP server-owned model selection maps to static account/route policy without browser authority, accidental active routing mutation, reserve promotion, live-model overclaim, or raw secret exposure.

## Result

- status: WBP_MODEL_SELECTION_ACCOUNT_ROUTE_TRUTH_CLASSIFIED
- final verdict: PASS_WITH_EXPLICIT_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: add and verify a bounded model-selection truth packet that accepts only server-issued `model_id`, classifies GPT account policy and external route policy statically, rejects browser route/backend/provider/base-url/token authority, redacts ids/auth refs, and keeps live/native/CLI/egress/E2E claims false.
- branch: codex/external-agent-lab-isolated
- head: 2f69f2505bd7fd1138df11554ab14cf05c6db803 at evidence capture time.
- touched files: wild_boar_proxy/codex_account_selection.py; tests/test_codex_account_selection.py; audit_results/wbp_account_route_model_selection_truth_2026-05-26/*
- tests run: python3 -m unittest -q tests.test_codex_account_selection tests.test_wbp_model_catalog_contract tests.test_codex_model_registry tests.test_cli_runner tests.test_operator_surface tests.test_closeout_resilience; python3 -m unittest -q tests.test_external_models tests.test_cli_external_models tests.test_external_agent_lab; python3 -m unittest -q tests.test_codex_custom_sessions; python3 -m unittest -q tests.test_cli; git diff --check
- blocked risks: UI import suites requiring `_tkinter` are blocked in the local Python environment; live model availability, live account health, native proof, CLI live prompt proof, direct egress proof, and final E2E remain out of scope.
- closure state: CLOSED

## Verification

- tests: focused and regression commands listed in Contour Capsule passed, including `tests.test_cli` with 412 tests.
- build: not applicable; Python unittest and whitespace checks passed.
- manual: no manual UI verification in scope.
- live verification: no live validation in scope; packet records static dry-run classification only.

## Artifacts

- spec: thread-only contour plan, not stored in repo.
- packet: audit_results/wbp_account_route_model_selection_truth_2026-05-26/model_to_route_selection_packet.json
- report: audit_results/wbp_account_route_model_selection_truth_2026-05-26/allowed_claims_matrix.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout creation time
- pushed: pending at closeout creation time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty historical evidence remains outside the staged contour scope.
- private-data risk reviewed: yes; packets contain redacted/hash refs only and no raw upstream tokens, auth headers, raw auth refs, prompt bodies, or current Codex auth material.

## Notes

- blockers encountered: local `_tkinter` is unavailable, so UI import suites were classified as environment-blocked rather than green.
- resume from here: CLOSED
