# Spec: Web Safe App Copy Launch Pass

## Objective

Add a web-managed, server-issued dry-run launch surface for a separate app copy and explicitly block live launch until a server-owned app copy contract is proven.

## In Scope

- Safe app copy launch mode metadata.
- Dry-run packet and endpoint.
- Conditional live endpoint that returns a blocked, non-launch packet.
- UI controls and packet projection.
- Browser dry-run click proof.
- Forbidden browser field rejection.

## Out of Scope

- Codex Custom session manager work.
- GPT accounts, API routes, model routing, and transcripts.
- CLIProxyAPI engine changes.
- Desktop packaging and installer.
- Design polish.
- Current Codex or `~/.codex` mutation.
- Production, desktop, account, rotation, load, or design readiness claims.

## Constraints

- Browser cannot provide path, app path, profile root, data dir, port, pid, env, HOME, CODEX_HOME, backend, route, token, auth, secret, API key, or authorization fields.
- Server-issued packet truth is required before any green UI state.
- Live launch is blocked in this contour unless a separate owner contract exists.
- Raw paths, pid, and env values must not be rendered to the browser.

## Assumptions

- Existing operator dispatch surfaces are not the owner for this contour.
- A dry-run-ready verdict is valid if live launch is explicitly not admitted and no process is launched.
- The next contour can add an app copy owner contract before attempting bounded live launch.

## Acceptance Criteria

- [x] Dry-run endpoint returns server-issued separate app copy plan.
- [x] Forbidden browser fields are rejected.
- [x] UI button is wired and not a no-op.
- [x] UI shows current Codex isolation proof.
- [x] Live launch endpoint blocks without launching.
- [x] Browser proof confirms dry-run packet and disabled live button.
- [x] Final verdict remains `WEB_SAFE_APP_COPY_LAUNCH_DRY_RUN_READY`.

## Verification

- tests: launch mode, live server, UI, and operator surface tests.
- build: Python compile, Node syntax, and diff check.
- manual: Browser dry-run click proof.
- live evidence: dry-run, live-blocked, isolation, and browser projection packets.

## Open Questions

- The next launch contour should define the server-owned app copy owner contract required before live launch can be admitted.
