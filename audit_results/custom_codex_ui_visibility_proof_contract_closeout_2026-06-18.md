# Custom Codex UI Visibility Proof Contract Closeout

## Goal

Add a strict file-backed command packet that joins an existing Custom Codex
visible-source binding proof with a native Custom Codex UI observer packet, so
WBP can prove that a handoff-bound response was observed in the real Custom
Codex UI without treating screenshots, WBP UI state, or transcript-only evidence
as UI truth.

## Result

- status: closed
- final verdict: Custom Codex UI visibility proof contract, CLI surface, and fail-closed negative matrix added and verified
- closure state: CLOSED

## Contour Capsule

- goal: add `router-hook custom-codex-ui-visibility-proof` that consumes a visible-source binding proof plus a native `custom_codex_native_prompt_submit` observer packet and emits `custom_codex_ui_visibility_proven=true` only when the response token is request-bound, handoff-digest-bound, profile/process-bound, and observed through the approved CDP renderer scan
- branch: `codex/stabilize-runtime-core`
- head: `b498b99e` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_ui_visibility_proof.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_ui_visibility_proof.py`, `audit_results/custom_codex_ui_visibility_proof_contract_closeout_2026-06-18.md`
- tests run: `python3 -m py_compile wild_boar_proxy/custom_codex_ui_visibility_proof.py wild_boar_proxy/cli.py tests/test_custom_codex_ui_visibility_proof.py`; `python3 -m unittest tests.test_custom_codex_ui_visibility_proof tests.test_custom_codex_visible_source_binding_proof tests.test_native_launch_dispatch`; `make test-core`; `python3 -m unittest tests.test_cli`; `git diff --check`
- blocked risks: independent audit found request-id prefix truncation could weaken strict binding for overlong ids; fixed by validating full request id before binding and adding a regression test
- closure state: CLOSED

## Verification

- tests: new UI visibility proof suite passed 14 tests; adjacent visible-source/native stack passed 110 tests; `make test-core` passed 418 tests and 120 subtests; full CLI suite passed 496 tests
- build: `python3 -m py_compile wild_boar_proxy/custom_codex_ui_visibility_proof.py wild_boar_proxy/cli.py tests/test_custom_codex_ui_visibility_proof.py` passed
- manual: independent read-only audit reported one Medium request-id truncation issue; the issue was fixed and covered by `test_blocks_overlong_request_id_without_prefix_truncation`
- live verification: not executed in this contour; no live Custom Codex UI end-to-end success is claimed by this closeout

## Artifacts

- spec: current task-thread contour text only; no repo-resident forward plan
- packet: `router-hook custom-codex-ui-visibility-proof` command surface
- report: this closeout file

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files `tests/test_web_design_ui.py` and `wild_boar_proxy/web_design_ui/scripts/overview.js` were not edited for this contour and are excluded from staging
- private-data risk reviewed: yes; expected visible text is accepted only as a redaction secret and is not recorded, raw prompt/text/DOM/provider/backend details are rejected, file paths are not recorded, and route/provider values are not introduced by this proof

## Notes

- blockers encountered: full request-id binding had to be hardened after independent audit; overlong ids now block instead of truncating to a prefix
- residual boundary: this contour proves the strict verifier and CLI contract for Custom Codex UI visibility; it does not claim product readiness, native free-chat router readiness, or a completed live UI run
- resume from here: CLOSED
