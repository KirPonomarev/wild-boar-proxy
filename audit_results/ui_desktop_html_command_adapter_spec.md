# UI_DESKTOP_HTML_COMMAND_ADAPTER_BOUNDARY Spec

## Contour

- `CONTOUR_ID`: `UI_DESKTOP_HTML_COMMAND_ADAPTER_BOUNDARY`
- `CONTOUR_CLASS`: `CODE_PLUS_TESTS_PLUS_AUDIT_ARTIFACTS`
- `DATE`: `2026-05-09`
- `BASE_BRANCH`: `codex/ui-desktop-html-static-overview-fixtures`
- `WORK_BRANCH`: `codex/ui-desktop-html-command-adapter-boundary`

## Goal

Create the single backend-side command adapter boundary for the desktop HTML UI
without live browser binding, runtime-core edits, direct state/log reads, or
deferred rollout controls.

## Canon Binding

This contour follows the repo canon order from `AGENTS.md`:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

`WORKFLOW_OS_V1_2.md` governs execution process only and does not override
runtime/product canon.

## Write Surfaces

- `wild_boar_proxy/desktop_ui/command_adapter.py`
- `wild_boar_proxy/desktop_ui/README.md`
- `tests/test_desktop_ui_command_adapter.py`
- `tests/test_desktop_ui_static.py`
- `audit_results/ui_desktop_html_command_adapter_spec.md`
- `audit_results/ui_desktop_html_command_adapter_packet.json`
- `audit_results/ui_desktop_html_command_adapter_closeout.md`

## Explicit Non-Scope

- No live JavaScript/browser command binding.
- No `web_ui` changes.
- No `ui_shell.py` changes.
- No CLI/runtime command implementation changes.
- No execution-core behavior changes.
- No renderer package or dependency decision changes.
- No rollout/stage/policy/evidence actions exposed.

## Adapter Law

- Renderer-facing code selects only canonical adapter command IDs.
- The adapter maps IDs to fixed argv arrays.
- No free-form shell string is accepted.
- `shell=True` is forbidden.
- Command stdout must be exactly one JSON object.
- Exit code alone is not success.
- Top-level packet `status` and `machine_error_code` remain authoritative.
- Invalid JSON, empty stdout, extra stdout, missing required fields, timeout,
  runner exception, and forbidden commands become `integration_failure`.
- Top-level command packet errors become `command_error`, not green success.
- `stderr` is retained as support detail only and never runtime truth.
- No direct state-file, log, registry, supervisor, or cache fallback exists.

## Allowlist

Read commands:

- `status`
- `healthcheck`
- `mode.get`
- `accounts.list`
- `rollout.rotation.inspect`

Action commands:

- `mode.set.stable`
- `mode.set.managed`
- `sync`
- `launch.client`
- `launch.smoke`
- `stable.repair.dry_run`
- `stable.repair.apply`
- `accounts.onboard`
- `accounts.validate`
- `accounts.promote`
- `accounts.demote`
- `accounts.hold`
- `accounts.release`
- `accounts.retire`
- `diagnostics.export`

## Forbidden First-Pass Commands

- `policy stage ...`
- `rollout stage ...`
- `rollout evidence capture ...`
- `stable target switch ...`
- Any command not explicitly allowlisted.

## Acceptance

- Allowlisted commands build argv-list calls only.
- Disallowed commands are rejected before runner execution.
- Structured account `id` argument is passed as a single argv element.
- Missing structured arguments fail closed.
- Valid JSON packets normalize to adapter result.
- Invalid JSON does not become success.
- Extra stdout after JSON does not become success.
- Required top-level packet fields are enforced.
- Top-level error packets remain visible as `command_error`.
- Timeout is represented as `integration_failure`.
- Existing static desktop UI remains fixture-only and does not import adapter.
