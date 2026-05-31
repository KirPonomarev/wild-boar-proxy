# Spec: WEB_FUNCTIONAL_SURFACE_INVENTORY_AND_ADMISSION_MATRIX_PASS

## Objective

Build a canonical technical inventory/admission matrix for all implemented WBP command-owner capabilities and current web UI surfaces before any broad web wiring.

## In Scope

- Read `COMMAND_API.md`, `web_design_command_adapter.py`, `web_design_live_server.py`, `overview.js`, and `index.html`.
- Classify command API surfaces, adapter CommandSpec entries, UI_ACTION_ALLOWLIST actions, frontend action references, and model/Codex engine status surfaces.
- Capture live `/api/*` readonly/action endpoints if `127.0.0.1:8788` is available.
- Produce machine-readable inventory, gap matrix, proof, independent audit, and closeout.

## Out of Scope

- New backend behavior.
- New frontend wiring.
- Runtime/account/API mutation.
- Rollout, package, installer, reset, uninstall activation.
- Design polish.
- Current Codex mutation.

## Constraints

- Canon order: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, STATE_SCHEMA.md, COMMAND_API.md, DELIVERY_RULES.md, README.md, WORKFLOW_OS_V1_2.md, AGENTS.md.
- Browser must not send `api_key`, `secret`, `token`, raw `auth`, or raw local `path`.
- `route_id`, `backend_id`, and `account_id` are server-issued only when exposed to browser payloads.
- High-risk surfaces must be classified, not silently activated.
- Live endpoint unavailable is recorded as `live_unavailable`, not inferred as success.

## Assumptions

- `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` is not truthfully earned, so this is not rich UI expansion.
- Existing web files may already contain controls; this contour classifies them without changing behavior.
- Agent spawn can be unavailable; local replay audit is acceptable if the failure is recorded.

## Acceptance Criteria

- [x] Every `COMMAND_API.md` required command is classified.
- [x] Every adapter `CommandSpec` is classified.
- [x] Every `UI_ACTION_ALLOWLIST` action is classified.
- [x] Every current frontend action reference found by static scan is classified.
- [x] Live `/api/*` entries are classified as captured or `live_unavailable`.
- [x] High-risk/destructive/release/host launch surfaces are deferred.
- [x] Model surfaces distinguish available/configured/selected/applied/provider-native.
- [x] Server-issued ID rule is recorded for account/route/backend IDs.
- [x] No backend or frontend behavior changed.
- [x] Next contour is bounded to `WEB_CORE_ACTIONS_WIRING_PASS`.

## Verification

- tests: `python3 tools/check_closeout_resilience.py --staged-only`; `git diff --check`
- build: not applicable, no code behavior changed
- manual: static inventory/audit generated from source files
- live evidence: {"api/actions": "live_unavailable", "api/live-readonly": "live_unavailable", "api/accounts-readonly": "live_unavailable", "api/api-connections-readonly": "live_unavailable"}

## Open Questions

- Which safe candidate should be wired first inside `WEB_CORE_ACTIONS_WIRING_PASS` after owner review?
