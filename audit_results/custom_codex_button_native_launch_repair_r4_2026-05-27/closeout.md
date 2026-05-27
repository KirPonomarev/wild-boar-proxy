# CUSTOM_CODEX_BUTTON_NATIVE_LAUNCH_REPAIR_R4 Closeout

## Goal

Make the WBP `Запустить клиент` button truthfully launch Custom Codex native app/window, and allow green success only when native launch proof actually exists.

## Result

- status: ok
- final verdict: `CUSTOM_CODEX_BUTTON_NATIVE_LAUNCH_WORKS_TRUTHFULLY`
- closure state: CLOSED

## Contour Capsule

- goal: replace dispatch-only launch semantics with owner-authorized Custom native launch semantics and remove false-green proof collapse
- branch: `codex/external-agent-lab-isolated`
- head: `6a134929`
- touched files: `wild_boar_proxy/native_window_probe.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `tests/test_native_launch_dispatch.py`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`, `audit_results/custom_codex_button_native_launch_repair_r4_2026-05-27/*`
- tests run: `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile wild_boar_proxy/native_window_probe.py wild_boar_proxy/web_design_live_server.py tests/test_native_launch_dispatch.py tests/test_web_design_live_server.py tests/test_web_design_ui.py`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_native_launch_dispatch tests.test_web_design_live_server tests.test_web_design_ui`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `git diff --check`
- blocked risks: live packet still reported `native_app_usable=false`; closure kept launch proof at process plus pid-bound native window level and did not promote usability proof
- closure state: CLOSED

## Verification

- tests: `Ran 228 tests in 37.743s` -> `OK`
- build: Python compile slice passed; `node --check` passed
- manual: overview and settings launch controls are wired to `launch_custom_client_native`
- live verification: `curl http://127.0.0.1:8788/api/actions` returned `launch_custom_client_native.available=true`, `availability_state=displayable_readonly`; `curl -H 'Content-Type: application/json' -d '{"ui_action":"launch_custom_client_native"}' http://127.0.0.1:8788/api/action` returned `status=ok`, `result.status=ok`, `process_started=true`, `expected_custom_identity_observed=true`, `native_window_observed=true`, `native_app_usable=false`, `real_codex_app_launched=true`

## Artifacts

- spec: thread-only contour `CUSTOM_CODEX_BUTTON_NATIVE_LAUNCH_REPAIR_R4`
- packet: `audit_results/custom_codex_button_native_launch_repair_r4_2026-05-27/*.json`
- report: `audit_results/custom_codex_button_native_launch_repair_r4_2026-05-27/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit set: this closeout is intended to travel only inside the logically complete contour commit set
- push state: contour is closed only together with the pushed branch state that carries this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; browser authority fields remained forbidden and live proof packet remained redacted

## Notes

- blockers encountered: initial false-green risk in pid/name window proof; initial metadata mismatch between full-phase UI availability and owner authorization; both were repaired and reverified; final UI debug packet now also preserves `real_codex_app_launched` without promoting `native_app_usable`
- resume from here: CLOSED
