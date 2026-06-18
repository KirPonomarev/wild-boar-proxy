# Custom Codex Visible-Source Binding Closeout

## Goal

Prove that a completed Custom Codex working-flow delivery has an approved visible
source that is digest-bound to the same handoff, without claiming rendered UI
visibility or product readiness.

## Result

- status: closed
- final verdict: visible-source binding proof added and verified
- closure state: CLOSED

## Contour Capsule

- goal: add a file-backed `router-hook visible-source-binding-proof` packet that consumes a working-flow delivery proof plus Codex exec JSONL and proves `visible_source_bound_to_handoff=true`
- branch: `codex/stabilize-runtime-core`
- head: `9683bb10aafe` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_visible_source_binding_proof.py`, `wild_boar_proxy/codex_transcript_delivery_observation.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_visible_source_binding_proof.py`, `tests/test_cli.py`, `audit_results/custom_codex_visible_source_binding_closeout_2026-06-18.md`
- tests run: py_compile for touched Python files; `python3 -m unittest tests.test_custom_codex_visible_source_binding_proof`; adjacent proof stack with 53 tests; CLI effect inventory with 21 tests; broader Custom Codex proof stack with 108 tests; `make test-core`; `python3 -m unittest tests.test_cli tests.test_cli_external_models`; `git diff --check`
- blocked risks: non-UTF-8 proof/JSONL evidence crash found by independent audit and fixed fail-closed with regression tests
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_custom_codex_visible_source_binding_proof` passed 12 tests; adjacent proof stack passed 53 tests; broader proof stack passed 108 tests; CLI full suite passed 528 tests
- build: `python3 -m py_compile wild_boar_proxy/custom_codex_visible_source_binding_proof.py wild_boar_proxy/codex_transcript_delivery_observation.py wild_boar_proxy/cli.py tests/test_custom_codex_visible_source_binding_proof.py` passed
- manual: independent read-only audit reported one P1 fail-closed gap; the gap was fixed and covered
- live verification: `/tmp/wbp-custom-codex-visible-source-binding-proof.json` returned `status=ok`, `machine_error_code=OK`, `visible_source_observed=true`, `visible_source_bound_to_handoff=true`, `visible_source_after_delivery=true`, `route_secret_screening_proven=true`, `fallback_used=false`, `local_imitation_used=false`, `native_codex_subagent_used_as_dip=false`, `custom_codex_ui_visibility_proven=false`, `product_ready=false`

## Artifacts

- spec: current task-thread contour text only; no repo-resident forward plan
- packet: `/tmp/wbp-custom-codex-visible-source-binding-proof.json`
- report: this closeout file

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files `tests/test_web_design_ui.py` and `wild_boar_proxy/web_design_ui/scripts/overview.js` were not edited for this contour and are excluded from staging
- private-data risk reviewed: yes; raw prompts, route ids, provider text, backend details, transcript JSONL, and evidence paths are not recorded in the success packet; runtime-context route ids are used only as leak-screening values

## Notes

- blockers encountered: non-UTF-8 evidence files previously escaped as traceback instead of strict JSON packet; fixed by catching `UnicodeDecodeError` in the working-flow proof reader and shared Codex JSONL reader
- residual boundary: this contour proves approved visible-source binding after working-flow delivery; it does not prove rendered Custom Codex UI visibility, native free-chat router readiness, or product readiness
- resume from here: CLOSED
