# CODEX_CUSTOM_APP_OPERATOR_SURFACE_MAIN_WEB_INTEGRATION_PASS Closeout

## Goal

Wire the hardened Codex Operator path into the main Wild Boar Proxy web Overview as one bounded operator action: server-issued model selection, one prompt through isolated Codex engine, machine-backed response packet, redacted transcript, and process-only isolation proof.

## Result

- status: passed
- final verdict: main web operator surface integration is proven for one bounded prompt path; global runtime claim gate remains blocked and is not closed by this contour
- next action: commit and push this contour, then plan the next runtime claim-gate or broader operator-surface contour

## Contour Capsule

- goal: main WBP web Overview can run one bounded Codex Operator prompt through WBP with server-issued model validation and separate process-only isolation proof
- branch: codex/external-agent-lab-isolated
- head: 734c5a2 contour commit
- touched files: wild_boar_proxy/operator_surface.py, wild_boar_proxy/web_design_live_server.py, wild_boar_proxy/web_design_ui/index.html, wild_boar_proxy/web_design_ui/scripts/overview.js, tests/test_operator_surface.py, tests/test_web_design_live_server.py, tests/test_web_design_command_adapter.py, audit_results/codex_custom_app_operator_surface_main_web_integration_pass_2026-05-23/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; python runtime unittest 619 tests OK; git diff --check; targeted operator/web adapter tests OK; browser click proof; process-only isolation proof
- blocked risks: runtime claim_gate remains blocked for active-only-traffic, pool-participation-correct, stable-15-proved; UI displays prompt ok / gate blocked and does not claim global runtime success
- next exact command: git push origin codex/external-agent-lab-isolated

## Verification

- tests: `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_operator_surface tests.test_cli tests.test_cli_external_models tests.test_external_models tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q` -> 619 tests OK
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> OK; `git diff --check` -> OK
- manual: Browser click proof on `http://127.0.0.1:8791/?source=live&screen=overview` returned `MAIN_WEB_OK`
- live verification: process-only proof returned `MAIN_WEB_PROCESS_OK`, `protected_surfaces_unchanged: true`, `tmp_root_removed: true`

## Artifacts

- spec: `audit_results/codex_custom_app_operator_surface_main_web_integration_pass_2026-05-23/spec.md`
- packet: `audit_results/codex_custom_app_operator_surface_main_web_integration_pass_2026-05-23/browser_proof.json`
- report: `audit_results/codex_custom_app_operator_surface_main_web_integration_pass_2026-05-23/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: 734c5a2 Integrate Codex operator surface into web UI
- pushed: pending push after closeout git-truth update

## Scope Check

- unrelated work mixed in: no; existing unrelated untracked files were ignored
- private-data risk reviewed: yes; `redaction_audit.json` reports no raw secret findings and browser DOM forbidden findings are empty

## Notes

- blockers encountered: missing `play-circle.png` asset was repaired by using existing `play.png`; stale allowlist test was updated for existing disabled provider credential adapter commands; independent auditor flagged false-green risk and UI was repaired to show `prompt ok / gate blocked`
- follow-up contour: runtime claim-gate repair or broader Codex Operator surface expansion with the same forbidden-field and server-issued-id discipline
- resume from here: CLOSED
