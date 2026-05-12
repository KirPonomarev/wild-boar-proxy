# UI Web First Screen Visual Check

Screen: `01_overview_dashboard`

## Reference

- Source package: `/Users/kirillponomarev/Desktop/кабан дизайн/эталон дизайна.zip`
- Reference PNG: `wild_boar_proxy_redesign/png/01_overview_dashboard.png`
- Reference PNG dimensions: `3200x2000`
- Intended CSS viewport: `1600x1000`

## Local Preview

- URL: `http://127.0.0.1:8787/?state=healthy`
- Static root: `wild_boar_proxy/web_design_ui`
- Fixture state checked: `healthy`

## Browser Smoke

Observed in the in-app browser:

- page title surface loads
- `Обзор` heading visible
- `WILD BOAR PROXY` brand visible
- `boar_mark.png` visible
- fixture warning visible
- healthy fixture renders as `Работает`
- action controls are disabled in this contour

## Visual Notes

- The implemented structure follows the reference: warm canvas, large left
  sidebar, boar mark, overview header, system card, mode card, KPI row, event
  list.
- The first screenshot check was captured in the in-app browser viewport, which
  is smaller than the full `1600x1000` baseline, so the right edge is cropped in
  that smoke capture.
- The CSS shell itself is fixed at `1600x1000`, matching the source HTML
  viewport and half-scale of the `3200x2000` PNG reference.

## Result

Visual admission passes for this contour as a fixture-backed first-screen web
transfer. Pixel-perfect baseline screenshot automation remains deferred until a
stable browser viewport capture path is available.
