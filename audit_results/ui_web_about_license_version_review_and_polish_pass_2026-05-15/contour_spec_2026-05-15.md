# UI_WEB_ABOUT_LICENSE_VERSION_REVIEW_AND_POLISH_PASS Spec

## Goal

Polish the existing Settings About block into a readonly product metadata surface
that states product role, license, UI mode, version/build limits, engine boundary,
and desktop approval status without implying release, package, runtime, or desktop
readiness.

## Scope

- `wild_boar_proxy/web_design_ui/index.html`
- `tests/test_web_design_ui.py`
- this contour audit directory

## Out Of Scope

- runtime, command adapter, allowlist, and live server changes
- package/build commands or browser access to git/package metadata
- desktop/native work
- license/legal file changes
- external support or release claims

## Acceptance Criteria

- About remains readonly metadata.
- Product is `Wild Boar Proxy`.
- License is `AGPL-3.0-or-later`.
- Role is `local control layer`.
- UI mode is `web design preview`.
- Version/build says it is not packaged and local preview is not published.
- Source revision is not exposed to browser UI.
- Runtime engine is described only as `CLIProxyAPI boundary`.
- Desktop status is owner-gated, not ready.
- Tests forbid fake version, release, production, desktop, support, package, and
  browser metadata-fetch claims.

## Stop Conditions

- Any need to rewrite license/legal terms.
- Any need for browser-side package, git, or runtime metadata fetching.
- Any production/release/desktop-ready claim.
- Any command adapter, runtime, or desktop scope change.
