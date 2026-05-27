# CUSTOM_CODEX_KEYCHAIN_PREFLIGHT_PRODUCT_INTEGRATION_PHASE1_R2 Closeout

## Goal

Productize the isolated-home keychain preflight for Custom Codex native launch on macOS without widening claims beyond prompt-avoidance truth.

## Result

- status: ok
- final verdict: `CUSTOM_CODEX_KEYCHAIN_PREFLIGHT_PHASE1_INTEGRATED_WITH_BOUNDARY`
- closure state: CLOSED

## Contour Capsule

- goal: integrate a server-owned isolated-HOME keychain preflight into the Custom native launch lane, record packet truth, and keep prompt-avoidance separate from auth proof
- branch: `codex/external-agent-lab-isolated`
- head: `d66d7348`
- touched files: `wild_boar_proxy/keychain_preflight.py`, `wild_boar_proxy/native_window_probe.py`, `tests/test_keychain_preflight.py`, `tests/test_native_launch_dispatch.py`, `audit_results/custom_codex_keychain_preflight_product_integration_phase1_r2_2026-05-28/*`
- tests run: `python3 -m py_compile wild_boar_proxy/keychain_preflight.py wild_boar_proxy/native_window_probe.py tests/test_keychain_preflight.py tests/test_native_launch_dispatch.py`; `python3 -m unittest tests.test_keychain_preflight tests.test_native_launch_dispatch`; `python3 -m pytest tests/test_web_design_live_server.py -k "custom_native_launch"`; `python3 - <<'PY' ... prepare_isolated_home_keychain(...) live helper verification ... PY`; `git diff --check`
- blocked risks: host-level prompt suppression through the product path is not closed in this contour; local collection of `tests/test_web_design_live_server.py` is blocked by missing `_tkinter` in the current Python environment
- closure state: CLOSED

## Verification

- tests: `Ran 39 tests in 0.015s` -> `OK`
- build: Python compile slice passed; `git diff --check` passed
- manual: none required in Phase 1
- live verification: live helper run returned `status=ok`, `isolated_default_keychain_verified=true`, `isolated_search_list_verified=true`; `security default-keychain -d user` was unchanged before/after the helper run

## Artifacts

- spec: thread-only contour `CUSTOM_CODEX_KEYCHAIN_PREFLIGHT_PRODUCT_INTEGRATION_PHASE1_R2`
- packet: `audit_results/custom_codex_keychain_preflight_product_integration_phase1_r2_2026-05-28/*.json`
- report: `audit_results/custom_codex_keychain_preflight_product_integration_phase1_r2_2026-05-28/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit set: this closeout is intended to travel only inside the logically complete contour commit set
- push state: contour is closed only together with the pushed branch state that carries this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; real keychain paths remained redacted, real user keychain was not mutated, and no keychain item reads were introduced

## Notes

- blockers encountered: local pytest collection of `tests/test_web_design_live_server.py` failed because `_tkinter` is unavailable in the active Python environment; an independent read-only audit initially found two material issues (late isolated-HOME write-surface guard and root-pid fallback in custom window proof), both were repaired and reverified before closeout; this contour therefore closes mechanism integration only and keeps host-level prompt suppression outside the claim boundary
- resume from here: CLOSED
