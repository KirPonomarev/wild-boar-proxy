# Spec: Web API Owner Credential Setup Pass

## Objective

Turn the current `api_route_connect` dead-end into a usable operator flow when the
owner credential for `openrouter` is missing.

## In Scope

- Surface `credential_missing` inline on Quick Start and API Connections.
- Reuse existing owner surfaces for credential status and route connect.
- Add bounded UI actions for credential check and retry connect.
- Keep browser payloads secret-free.
- Prove the missing-credential path in live browser behavior.

## Out of Scope

- Browser secret intake.
- OAuth/provider automation.
- New providers beyond `openrouter`.
- Desktop or packaging work.

## Constraints

- `CLIProxyAPI` remains the engine.
- Web remains a control layer.
- No `api_key`, `secret`, `token`, `path`, `auth`, or `route_id` from browser input.
- Connected state only after route validate plus refresh proof.

## Assumptions

- Owner credential may be absent from the live proof server environment.
- If env is added after the server starts, operator guidance may need to mention restart.
- Existing `external-models credentials status/admit` and route add/validate surfaces remain canonical.

## Acceptance Criteria

- [x] Missing credential is visible inline, not buried only in the lower action panel.
- [x] Quick Start and API Connections both expose a bounded owner setup lane.
- [x] `Проверить credential` uses existing credential status truth, not browser secrets.
- [x] `Повторить подключение` reuses the existing `api_route_connect` flow.
- [x] Browser payload remains secret-free.
- [x] Missing credential does not claim connected route state.

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_cli_external_models tests.test_external_models -q`
- build:
  - `git diff --check`
- manual:
  - live `api_route_connect` and `api_route_credential_check` on `127.0.0.1:8788`
- live evidence:
  - `audit_results/web_api_owner_credential_setup_pass_2026-05-22/evidence/browser-run-summary.json`

## Open Questions

- None for this contour; actual provider credential materialization remains owner-side by canon.
