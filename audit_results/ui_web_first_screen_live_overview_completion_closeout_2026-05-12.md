# UI Web First Screen Live Overview Completion Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_LIVE_OVERVIEW_COMPLETION`

## Result

The live overview now separates primary truth from warning evidence:

- `status`, `mode_get`, and `accounts_list` remain strict primary truth.
- `healthcheck` failure degrades live overview with a visible warning.
- `rollout_rotation_inspect` failure becomes a visible warning/event.
- Rotation contradiction no longer collapses the whole overview when primary
  truth is valid.

## Real Smoke

The local live server was started on `127.0.0.1:8788`.

`/api/live-readonly` returned:

```text
status=ok
ui_state=healthy
primary_truth_ok=true
has_warnings=true
warning_machine_error_code=ROTATION_EVIDENCE_CONTRADICTED
```

This is the intended behavior: primary overview truth rendered, rollout warning
remained visible, no stale-green hiding.

## Layer Check

- Browser fetches only `api/live-readonly`.
- Browser does not submit command IDs.
- Action buttons remain disabled.
- No direct runtime/state/log/registry parsing was introduced.
- `runtime.py`, `web_ui.py`, and `ui_shell.py` are not part of this contour.
- Current working tree still has pre-existing dirty `runtime.py` outside this
  contour; it is excluded from the contour commit.

## Verification

Completed:

```text
python3 -m unittest -q tests.test_web_design_live_server
python3 -m unittest -q tests.test_web_design_ui
python3 -m unittest -q tests.test_web_design_command_adapter
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui
python3 -m unittest -q tests.test_cli tests.test_cli_external_models tests.test_external_models
git diff --check
```

Independent audit result: PASS.
