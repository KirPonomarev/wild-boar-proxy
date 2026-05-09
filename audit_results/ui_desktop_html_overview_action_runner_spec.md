# UI_DESKTOP_HTML_OVERVIEW_ACTION_RUNNER Spec

## Contour

- `CONTOUR_ID`: `UI_DESKTOP_HTML_OVERVIEW_ACTION_RUNNER`
- `CONTOUR_CLASS`: `BACKEND_ONLY_CODE_PLUS_TESTS_PLUS_AUDIT_ARTIFACTS`
- `DATE`: `2026-05-09`
- `BASE_BRANCH`: `codex/ui-desktop-html-overview-live-read-binding`
- `WORK_BRANCH`: `codex/ui-desktop-html-overview-action-runner`

## Goal

Build the backend-only overview action runner for admitted overview actions
without browser click wiring, renderer bridge implementation, runtime/CLI
implementation changes, or live mutating smoke.

## Canon Binding

- Strict JSON command packets remain UI truth.
- Command exit code alone is not success.
- Confirmation is required before admitted mutating actions run.
- Post-action live overview refresh is mandatory.
- No false-green or stale-green path is allowed after action failure or refresh
  failure.
- Browser JavaScript must not execute arbitrary shell commands.
- UI must not parse state files, registry files, logs, or diagnostics bundles.

## Write Surfaces

- `wild_boar_proxy/desktop_ui/overview_actions.py`
- `wild_boar_proxy/desktop_ui/README.md`
- `tests/test_desktop_ui_overview_actions.py`
- `tests/test_desktop_ui_static.py`
- `audit_results/ui_desktop_html_overview_action_runner_spec.md`
- `audit_results/ui_desktop_html_overview_action_runner_packet.json`
- `audit_results/ui_desktop_html_overview_action_runner_closeout.md`

## Explicit Non-Scope

- No browser button enablement.
- No browser-to-backend bridge.
- No live mutating command smoke.
- No account lifecycle action execution.
- No diagnostics export action execution.
- No stable repair action execution.
- No rollout/stage/policy/evidence action execution.
- No `stable target switch` action execution.
- No runtime core, CLI implementation, `web_ui.py`, or `ui_shell.py` changes.

## Admitted Actions

- `switch_stable` -> `mode.set.stable`
- `switch_managed` -> `mode.set.managed`
- `run_sync` -> `sync`
- `launch_client` -> `launch.client`
- `run_smoke` -> `launch.smoke`

## Deferred Actions

- stable repair
- account lifecycle
- diagnostics export
- rollout/stage/policy/evidence
- stable target switch

## Acceptance

- Unknown and deferred action IDs return strict JSON and do not execute adapter.
- Missing confirmation returns strict JSON and does not execute adapter.
- Admitted confirmed actions execute only through `command_adapter.py`.
- Post-action snapshot refresh runs after admitted action execution.
- Command error, invalid JSON, and refresh failure cannot become success.
- Browser JS remains unwired to `overview_actions.py`.
