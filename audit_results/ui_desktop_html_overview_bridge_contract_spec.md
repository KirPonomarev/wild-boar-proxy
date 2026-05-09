# UI_DESKTOP_HTML_OVERVIEW_BRIDGE_CONTRACT Spec

## Contour

- `CONTOUR_ID`: `UI_DESKTOP_HTML_OVERVIEW_BRIDGE_CONTRACT`
- `CONTOUR_CLASS`: `BACKEND_CONTRACT_PLUS_TESTS_PLUS_AUDIT_ARTIFACTS`
- `DATE`: `2026-05-09`
- `BASE_BRANCH`: `codex/ui-desktop-html-overview-action-runner`
- `WORK_BRANCH`: `codex/ui-desktop-html-overview-bridge-contract`

## Goal

Define and implement the safe backend bridge contract for the desktop HTML
overview without enabling real browser click wiring, renderer IPC, runtime/CLI
implementation changes, or live mutating command smoke.

## Canon Binding

- Strict JSON packets remain UI truth.
- Browser/request input cannot carry raw commands, argv, paths, env, cwd, or
  runtime files.
- The bridge accepts fixed operation IDs only.
- Operation failure is never green.
- Snapshot path remains fixed by backend contract.
- Browser buttons remain deferred until a separate full implantation contour.

## Write Surfaces

- `wild_boar_proxy/desktop_ui/overview_bridge.py`
- `wild_boar_proxy/desktop_ui/README.md`
- `tests/test_desktop_ui_overview_bridge.py`
- `tests/test_desktop_ui_static.py`
- `audit_results/ui_desktop_html_overview_bridge_contract_spec.md`
- `audit_results/ui_desktop_html_overview_bridge_contract_packet.json`
- `audit_results/ui_desktop_html_overview_bridge_contract_closeout.md`

## Explicit Non-Scope

- No browser click wiring.
- No renderer bridge implementation.
- No confirmation UX.
- No live mutating command execution.
- No runtime core, CLI implementation, `web_ui.py`, or `ui_shell.py` changes.

## Allowed Operations

- `refresh_overview`
- `run_overview_action`

## Forbidden Request Fields

- `command`
- `argv`
- `shell`
- `path`
- `state_path`
- `log_path`
- `registry_path`
- `snapshot_path`
- `runtime_file`
- `env`
- `cwd`

## Acceptance

- Unknown operation returns strict JSON error.
- Forbidden request fields return strict JSON error before operation execution.
- Missing action ID returns strict JSON error.
- Refresh operation uses the live overview snapshot writer.
- Action operation delegates to the overview action runner.
- Browser JS remains unwired to `overview_bridge.py`.
