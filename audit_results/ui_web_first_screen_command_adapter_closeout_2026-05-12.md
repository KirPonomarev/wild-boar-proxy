# UI Web First Screen Command Adapter Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_COMMAND_ADAPTER_BOUNDARY`

## Scope Result

Implemented a standalone command adapter in
`wild_boar_proxy/web_design_command_adapter.py`.

The adapter:

- accepts explicit command IDs only
- renders command arguments from fixed templates
- rejects unknown command IDs before runner execution
- rejects unsupported structured args
- blocks the disabled `launch_client` command in this contour
- preserves top-level packet truth
- treats `status=ok`, `exit_code=0`, and `machine_error_code=OK` as the only
  success combination
- maps timeout/parse/packet/runner failures to visible integration failures

## Layer Check

- This contour does not modify `wild_boar_proxy/runtime.py`.
- Current working tree contains a pre-existing dirty `wild_boar_proxy/runtime.py`
  diff; it is explicitly excluded from this contour commit.
- No changes to `wild_boar_proxy/web_ui.py` in this contour.
- No changes to `wild_boar_proxy/ui_shell.py` in this contour.
- Static web-design HTML still does not execute live commands.
- `launch_client` remains disabled in the first-screen HTML and blocked by the
  adapter.

## Verification

Completed:

```text
python3 -m unittest -q tests.test_web_design_command_adapter
python3 -m unittest -q tests.test_web_design_ui
python3 -m unittest -q tests.test_ui_shell
python3 -m unittest -q tests.test_web_ui
python3 -m unittest -q tests.test_cli tests.test_cli_external_models tests.test_external_models
git diff --check
```

## Decision

The contour is ready to proceed to independent audit and commit if regression
checks remain green.
