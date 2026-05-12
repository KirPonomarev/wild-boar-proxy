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

## Visual Polish Update

Updated during `UI_WEB_FIRST_SCREEN_VISUAL_POLISH_AND_PARITY`:

- removed fixed `width=1600,height=1000` viewport metadata
- removed whole-window `transform: scale(...)` fit behavior
- added desktop browser containment with `width: min(1544px, calc(100vw - 56px))`
- changed the main content area to vertical scroll instead of horizontal clipping
- added desktop breakpoints for narrower browser windows
- kept mobile/adaptive layout out of scope
- retained fixture-only data and disabled action buttons

## Visual Notes

- The implemented structure follows the reference direction: warm canvas, large left
  sidebar, boar mark, overview header, system card, mode card, KPI row, event
  list.
- The CSS shell no longer relies on shrinking the whole UI below readable size.
- Very narrow viewports may still look compressed because mobile layout is out
  of scope; the accepted target is desktop browser containment at 100% zoom.

## Result

Visual admission passes for this contour as a fixture-backed first-screen web
transfer and polish pass. Pixel-perfect baseline screenshot automation remains
deferred until a stable browser viewport capture path is available.
