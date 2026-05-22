# WEB_API_ROUTE_CONNECT_SERVER_OWNED_PASS Closeout

## Goal

Add a real sandbox web action for API route connection where the browser never provides secrets, paths, token material, auth files, backend ids, or route ids; the server owns route admission and proves success through strict command packets plus `api-connections-readonly` refresh.

## Result

- status: implemented and verified
- final verdict: closed_success pending final commit/push
- next action: commit and push this contour, then continue toward provider-specific owner source/login if needed

## Contour Capsule

- goal: `Подключить API` in web Quick Start/API screen runs server-owned route connect in sandbox copy and proves route visibility by refresh.
- branch: codex/external-agent-lab-isolated
- head: final contour commit containing this closeout; see git log
- touched files: `wild_boar_proxy/web_design_command_adapter.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `tests/test_web_design_command_adapter.py`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`, audit artifacts under this directory
- tests run: `node --check`; targeted web design tests; full 662-test gate; external-models targeted tests; `git diff --check`; closeout resilience before commit
- blocked risks: real provider-specific OAuth/login remains out of scope; current proof uses server-owned sandbox route source and local provider probe
- next exact command: `git push origin codex/external-agent-lab-isolated` after commit

## Verification

- tests: all commands listed in `metrics.json` passed.
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed.
- manual: browser proof clicked `Подключить API`, confirmed action, observed route refresh.
- live verification: `browser-run-summary.json` shows routes 0 -> 1, `route_visible_after_refresh=true`, `action_machine_error_code=OK`, `action_connect_phase=created_and_validated`, no browser secret/path/route_id intake.

## Artifacts

- spec: `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/spec.md`
- packet: `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/evidence/browser-action-packet.json`
- report: `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/metrics.json`, `audit_results/web_api_route_connect_server_owned_pass_2026-05-22/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: final contour commit containing this closeout; see git log
- pushed: pending push

## Scope Check

- unrelated work mixed in: no; unrelated untracked files in the worktree were ignored
- private-data risk reviewed: yes; browser sandbox runtime directory was removed before commit; evidence packets do not expose secret values or route spec paths

## Notes

- blockers encountered: old proof server occupied port 8788; it was identified as a previous sandbox web proof process and stopped before this proof
- follow-up contour: provider-specific owner API source/login if we want a real external provider connect flow beyond sandbox route admission
- resume from here: CLOSED
