# UI Web First Screen Live Read-Only Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_LIVE_READONLY_BINDING`

## Result

Implemented a bounded live read-only path for the first web-design screen:

- `wild_boar_proxy/web_design_live_server.py`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `wild_boar_proxy/web_design_ui/index.html`
- `tests/test_web_design_live_server.py`

Fixture mode remains available. Live mode is selected through `?source=live` or
the source selector and fetches only `/api/live-readonly`.

## Layer Check

- Browser cannot submit command IDs.
- Browser cannot submit shell strings.
- `launch_client` remains disabled and is not called by the live endpoint.
- No direct runtime/state/log/registry parsing was introduced.
- `runtime.py`, `web_ui.py`, and `ui_shell.py` are not part of this contour.
- Current working tree still has a pre-existing dirty `runtime.py` outside this
  contour; it is excluded from the contour commit.

## Real Smoke

The local live server was started on `127.0.0.1:8788`.

`/api/live-readonly` returned `integration_failure` because the real
`rollout_rotation_inspect` command returned:

```text
ROTATION_EVIDENCE_CONTRADICTED
```

This is accepted for the contour because the UI must not render stale green when
a required read-only truth command reports an error.

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
