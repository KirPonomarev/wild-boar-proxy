# UI Web First Screen Overview Contour

Contour: `UI_WEB_FIRST_SCREEN_OVERVIEW_RENDER_TRANSFER`

Goal: transfer the `01_overview_dashboard` design frame into an isolated web UI
preview backed only by fixtures.

## Boundary

- UI/design layer only.
- No live command execution.
- No direct runtime, state, or log reads.
- No desktop shell work.
- No replacement of `wild_boar_proxy/web_ui.py`.
- No changes to `wild_boar_proxy/runtime.py` by this contour.

## Canon References

- `CANON.md`: Wild Boar Proxy is the managing layer; CLIProxyAPI remains the
  engine.
- `MASTER_PLAN.md`: companion UI belongs to the control layer, not a second
  engine or generic proxy manager.
- `UI_READINESS_SPEC.md`: UI must not infer runtime truth from files, logs,
  cached UI state, or narrative memory.
- `COMMAND_API.md`: future live binding must consume strict JSON packets; this
  contour intentionally does not bind live commands.

## Inputs

- `/Users/kirillponomarev/Desktop/кабан дизайн/эталон дизайна.zip`
- `wild_boar_proxy_redesign/html/01_overview_dashboard.html`
- `wild_boar_proxy_redesign/png/01_overview_dashboard.png`
- `wild_boar_proxy_redesign/assets/boar_mark.png`

## Output

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `wild_boar_proxy/web_design_ui/assets/boar_mark.png`
- `wild_boar_proxy/web_design_ui/fixtures/*.json`
- `tests/test_web_design_ui.py`

## Scope Result

The contour creates an isolated fixture-backed design preview. It does not
modify the existing operator fallback UI or runtime owner surfaces.
