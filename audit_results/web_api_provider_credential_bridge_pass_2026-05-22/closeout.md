# WEB_API_PROVIDER_CREDENTIAL_BRIDGE_PASS Closeout

## Goal

Make web `Подключить API` use the owner credential surface before connecting the server-owned API route, without accepting or exposing browser secrets.

## Result

- status: implemented and verified
- final verdict: closed_success
- next action: continue to provider-specific dashboard/OAuth-style UX only if required

## Contour Capsule

- goal: web click runs `api_route_connect`, proves owner credential admission, route add/validate, readonly refresh, and ledger phase.
- branch: codex/external-agent-lab-isolated
- head: final contour commit containing this closeout; see git log
- touched files: `wild_boar_proxy/web_design_command_adapter.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `tests/test_web_design_command_adapter.py`, `tests/test_web_design_live_server.py`, audit artifacts under this directory
- tests run: `node --check`; required 175-test unittest gate; `git diff --check`; closeout resilience before commit
- blocked risks: real provider dashboard/OAuth UX remains out of scope; this contour uses owner-env credential admission and a local mock provider proof
- next exact command: start the next contour only after this commit is pushed

## Verification

- unit/browser-adjacent tests: `Ran 175 tests ... OK`
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed
- whitespace: `git diff --check` passed
- browser proof: canonical URL `http://127.0.0.1:8788/?screen=quick-start&source=live` clicked `Подключить API`, confirmed action, and refreshed API state
- action packet: `credential_status=missing`, `credential_admit_status=admitted`, `credential_phase=credential_admitted`, `api_route_connect_phase=created_and_validated`, `validate_status=ok`
- refresh proof: `api-connections-readonly` shows `wbp-web-primary-openrouter` enabled with `secret_status_label=available` and `validation_label=ok`
- ledger proof: UI ledger includes `credential_phase=credential_admitted`, `browser_api_key_intake=false`, `secret_exposed=false`
- redaction: sentinel owner credential was absent from all text evidence

## Artifacts

- spec: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/spec.md`
- metrics: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/metrics.json`
- independent audit: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/independent_audit.json`
- browser packet: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/evidence/browser-action-packet.json`
- browser summary: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/evidence/browser-run-summary.json`
- screenshot: `audit_results/web_api_provider_credential_bridge_pass_2026-05-22/evidence/browser-api-credential-bridge-after.png`

## Git

- branch: codex/external-agent-lab-isolated
- commit: final contour commit containing this closeout; see git log
- pushed: completed during contour closeout

## Scope Check

- unrelated work mixed in: no; unrelated untracked files in the worktree were ignored
- layer boundary: web remains control layer; credential materialization stays owner/server side
- private-data risk reviewed: yes; sandbox runtime stayed under temporary OS directories, and secret values are not present in committed evidence

## Notes

- blockers encountered: in-app browser does not expose network interception, so the browser proof used a local logging proxy on canonical port `8788` forwarding to the web server on `8790`; the browser still interacted with `8788`.
- follow-up contour: provider-specific dashboard/OAuth-style UX if required.
- resume from here: CLOSED
