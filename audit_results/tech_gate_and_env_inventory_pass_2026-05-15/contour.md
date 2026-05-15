# TECH_GATE_AND_ENV_INVENTORY_PASS

## Goal

Build a factual inventory of current repo surfaces, live-server entrypoints,
UI-admitted actions, payload boundaries, and plan/code/doc contradictions before
any live-readonly admission or sandbox work begins.

## Scope

- Read-only inspection of canon and repo wiring
- Read-only classification of commands, endpoints, and UI actions
- Cross-check of current `MASTER_PLAN.md` against live-server and UI exposure
- Audit artifact generation only

Out of scope:

- live mutations
- sandbox creation
- onboarding execution
- mode changes
- launch dispatch
- diagnostics export execution
- import/init/reset/uninstall execution

## Preflight

- `git status --short --untracked-files=no` -> clean
- `git log --oneline -n 12` -> current head `1f10e34 Revise master plan live sandbox sequence`
- `git config --get core.hooksPath` -> `/Volumes/Work/wild-boar-proxy/.githooks`
- `ls -la .githooks` -> tracked pre-commit hook present

## Findings

- Actual CLI entrypoints:
  - `wild_boar_proxy/__main__.py` -> `python -m wild_boar_proxy`
  - `wild_boar_proxy/cli.py` -> command-tree owner
- Actual live-web entrypoints:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_ui.py`
- `web_design_live_server` readonly GET endpoints are explicit:
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`
  - `/api/actions`
- `web_design_live_server` also exposes mutation gateway:
  - `POST /api/action`
- Adapter allowlist count: `27`
- UI action metadata count: `22`
- UI actions available without `--launch-client-path`: `21`
- Browser payload gate is narrow:
  - admitted browser key: `ui_action`
  - additionally bounded keys: `account_id`, `route_id`
  - browser-supplied `command_id`, `argv`, `path`, `token`, `secret`,
    `client_path`, `bundle_path`, and similar fields are blocked
- Current live-readonly wave contradiction:
  - `MASTER_PLAN.md` parks onboarding, lifecycle mutation, route mutation,
    runtime sync, launch, and diagnostics until live-readonly and sandbox
    boundaries are proven
  - `/api/actions` still reports those actions as available in current metadata
  - `overview.js` enables account, onboard, runtime, and non-deferred route
    buttons whenever source is `live`
- Current doc/code contradiction:
  - `wild_boar_proxy/web_design_ui/README.md` says live read-only mode "does not
    enable action buttons"
  - current server metadata and client availability logic do enable most
    allowlisted actions on `?source=live`

## Main Interpretation

The tech gate did its job: the surfaces are mapped, but the corrected
live-readonly wave is **not yet coherently enforced**. We should not move to
`WEB_LIVE_SERVER_READONLY_ADMISSION_PASS` while the current live server and UI
still expose parked mutation actions as available on the live source.

## Decision

- status: `STOP_AND_DIAGNOSE`
- reason:
  - tracked repo is clean
  - entrypoints and payload guards are now localized
  - current plan/code/doc contradictions are real and actionable
  - the next contour cannot honestly be "live-readonly admission" until parked
    mutation exposure is aligned with the corrected master plan

## Required Next Guardrails

- align `/api/actions` availability with the corrected parked-mutation policy
- keep `POST /api/action` out of the live-readonly wave until sandbox admission
- make the README match actual action enablement, or make code match README
- rerun tech-gate or readonly admission only after the action-parking mismatch is
  removed
