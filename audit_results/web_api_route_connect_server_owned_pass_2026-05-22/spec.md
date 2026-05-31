# Spec: WEB_API_ROUTE_CONNECT_SERVER_OWNED_PASS

## Objective

Deliver a practical web API connect action in sandbox copy: the browser can press `Подключить API`, but it does not provide route id, secrets, tokens, paths, auth, files, or backend ids. The server owns the route source, calls the external-models owner command surface, validates the route, and requires an `api-connections-readonly` refresh for visible success.

## In Scope

- Add `api_route_connect` to the web action allowlist for sandbox actions.
- Add disabled adapter command `external_models_routes_add_server_owned` mapped to `external-models routes add --file {route_spec_ref} --json`.
- Generate a bounded server-owned route spec inside the sandbox external-models directory.
- Run `external-models routes add --file ... --json` and `external-models routes validate --route ... --json` from the server side.
- Keep the browser payload to `ui_action` only for connect.
- Prove route visibility through `api-connections-readonly` after refresh.
- Add targeted tests and browser proof artifacts.

## Out of Scope

- Browser secret entry, token entry, file picker, local path input, or browser-selected route id.
- Desktop, packaging, broad external-models redesign, API route editor, provider OAuth.
- Runtime readiness claims beyond provider-route validation and readonly route visibility.

## Constraints

- Canon order: `CANON.md`, `MASTER_PLAN.md`, `RUNTIME_CONTRACT.md`, `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Wild Boar Proxy remains the control layer; external-models owner commands remain the mutation surface.
- Success is not inferred from UI text alone; success requires owner packet plus readonly refresh.
- Action result must not expose raw route spec paths or secret values.

## Acceptance Criteria

- [x] `api_route_connect` is available only in admitted sandbox action phase.
- [x] Browser request for connect contains no secret/path/token/auth/backend_id/route_id.
- [x] Server-owned route spec is used as the only add source.
- [x] Server calls `external-models routes add --file ... --json`.
- [x] Server calls `external-models routes validate --route ... --json`.
- [x] Refresh shows `wbp-web-primary-openrouter` in `api-connections-readonly`.
- [x] Action ledger records `api_route_connect`.
- [x] Tests and browser proof pass.

## Verification

- tests: see `metrics.json`.
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed.
- manual: browser proof at canonical URL `http://127.0.0.1:8788/?screen=quick-start&source=live` passed.
- live evidence: `evidence/browser-run-summary.json`, `evidence/browser-action-packet.json`, `evidence/browser-api-connections-after.json`.

## Open Questions

- Real provider-specific login/OAuth remains a later owner-source contour; this contour proves server-owned route admission and route validation without browser secret intake.
