# TECH_GATE_AND_ENV_INVENTORY_PASS

## Goal

Build a factual inventory of command surfaces, live-server endpoints, UI-admitted
actions, payload boundaries, and next-step risks before any live-readonly
admission or sandbox work begins.

## Scope

- Read-only inspection of canon and repo wiring
- Read-only classification of commands, endpoints, and UI actions
- Audit artifact generation only

Out of scope:

- live mutations
- sandbox creation
- onboarding
- mode changes
- launch dispatch
- diagnostics export
- import/init/reset/uninstall

## Preflight

- `git status --short --untracked-files=no` -> clean
- `git log --oneline -n 10` -> latest closed contour `42f1c16 Repair web UI visual QA defects`
- `bash tools/install_git_hooks.sh` -> hooks path configured

## Findings

- Canon-required commands listed in `COMMAND_API.md`: 30
- Repo-wired canon-required commands in adapter: 17
- Missing canon-required commands in current adapter wiring: 13
- Live server readonly GET endpoints are localized and explicit:
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`
  - `/api/actions`
- Live server also exposes mutation gateway:
  - `POST /api/action`
- UI-admitted actions exposed by metadata: 22
- Browser payload guard is narrow:
  - allowed keys are `ui_action` plus bounded `account_id` or `route_id`
  - unsupported browser keys are blocked before adapter dispatch

## Main Interpretation

The current repo is ready for a **readonly live-server admission contour**, but
not for blind live interaction. The next contour must treat `POST /api/action`
as forbidden and remain GET-only.

## Decision

- status: `GO_TO_WEB_LIVE_SERVER_READONLY_ADMISSION`
- reason:
  - tracked repo is clean
  - readonly surfaces are localized
  - payload boundaries are narrow and explicit
  - mutation surfaces are visible and classifiable
  - no canon/code contradiction blocks readonly admission

## Required Next Guardrails

- use live server only through readonly GET endpoints
- do not invoke `POST /api/action`
- do not treat `api/actions` metadata as runtime proof
- keep fixture and live truth separate
- treat missing canon-required commands as later admission/implementation work,
  not as proof blockers for readonly admission
