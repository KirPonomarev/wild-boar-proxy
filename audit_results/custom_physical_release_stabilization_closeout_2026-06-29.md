<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Physical Release Stabilization Closeout

## Goal

Close the release-stabilization tail for the Custom Codex path by preserving the
physical Custom evidence, keeping DeepSeek as the default API lane, fixing the
false-green observer/exact-output gaps, confirming fail-closed alias handling,
and hardening remaining runtime write helpers through the shared state-store
path.

## Result

- status: ok
- final verdict: Custom physical release gate, fast workflow gate, runtime write hardening, and full pytest release gate passed
- closure state: CLOSED

## Contour Capsule

- goal: close Custom physical release stabilization and residual hardening without adding product features or weakening owner-proof/security behavior
- branch: codex/stabilize-runtime-core
- head: 8ba1f975 pre-closeout worktree head; closeout created in the same worktree after green verification
- touched files: tests/test_api_agent_auto_router.py; tests/test_custom_codex_physical_observer.py; tests/test_custom_codex_physical_smoke.py; tests/test_external_models.py; tests/test_runtime_atomic_write.py; tests/test_state_store_atomic_write.py; tests/test_wbp_dip_tool.py; tests/test_web_design_live_server.py; tools/custom_codex_physical_smoke.py; wild_boar_proxy/api_agent_auto_router.py; wild_boar_proxy/cli.py; wild_boar_proxy/custom_codex_physical_observer.py; wild_boar_proxy/runtime.py; wild_boar_proxy/state_store.py; wild_boar_proxy/wbp_dip_tool.py; wild_boar_proxy/web_design_live_server.py; audit_results/custom_physical_release_stabilization_closeout_2026-06-29.md
- tests run: python3 -m pytest tests/test_state_store_atomic_write.py tests/test_runtime_atomic_write.py tests/test_external_models.py -q; python3 -m pytest tests/test_makefile_test_fast_contract.py -q; make test-fast; python3 -m pytest -q
- blocked risks: release gate was blocked until physical Custom matrix, fast workflow gate, shared write hardening, and full pytest all produced concrete green evidence; earlier physical blocked packets were retained as diagnostic evidence and superseded by green reruns
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_state_store_atomic_write.py tests/test_runtime_atomic_write.py tests/test_external_models.py -q` passed with 64 tests and 40 subtests
- tests: `python3 -m pytest tests/test_makefile_test_fast_contract.py -q` passed with 1 test
- tests: `make test-fast` passed with 456 tests and 125 subtests
- tests: `python3 -m pytest -q` passed with 4318 tests, 1 skipped test, and 971 subtests in 1235.37 seconds
- build: pytest suite imported and exercised the touched Python modules successfully
- manual: physical Custom evidence under `/tmp/wbp-manual-custom-evidence/custom-physical-release-gate-20260629` contains packet-backed UI runs for API alias casing, unknown-alias fail-closed behavior, native GPT aliases, GPT plus API dual lane, renamed aliases, DeepSeek level sweep, and repo-bridge strong tasks
- live verification: final Custom physical smoke packet under `/tmp/wbp-manual-custom-evidence/final-after-full-pytest-physical-20260629/packet.json` reported status `ok`, machine_error_code `OK`, owner proof `ok`, exact token observed, and response bound to the submitted request

## Artifacts

- spec: no new repo-resident active plan or spec was created for this stabilization tail
- packet: `/tmp/wbp-manual-custom-evidence/custom-physical-release-gate-20260629`
- packet: `/tmp/wbp-manual-custom-evidence/final-after-full-pytest-physical-20260629/packet.json`
- report: this closeout

## Git

- branch: codex/stabilize-runtime-core
- commit: not created by operator request in this turn
- pushed: not performed by operator request in this turn

## Scope Check

- unrelated work mixed in: no unrelated feature work was intentionally added; existing worktree changes from the Custom stabilization contour remain in scope
- private-data risk reviewed: yes; physical packets store hashes/booleans and do not record raw prompt text, raw Custom transcript text, raw CDP URL, profile path, user-data path, or secrets

## Notes

- blockers encountered: physical Custom observer false-green detection and exact-output parsing gaps were fixed before the final green gates
- resume from here: CLOSED
