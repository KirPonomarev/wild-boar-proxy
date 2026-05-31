<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Final Design Package Icon Policy

Contour: `UI_FINAL_DESIGN_PACKAGE_INTAKE_LOCK`

Date: `2026-05-14`

## Source Labels

- Design package: `owner_supplied_final_design_package`
- Icon package: `owner_supplied_phosphor_regular_icons`
- Logo asset: `owner_supplied_logo_asset`

These labels intentionally replace private source paths.

## Icon Rule

Use the owner-supplied Phosphor regular icon set as the visual source for app
icons. Do not commit the full icon archive or a full extracted icon dump.

## Allowed Future Asset Handling

- Copy only icons needed by implemented screens.
- Prefer regular-weight icons unless a screen-specific design requires a
  different weight and the change is recorded.
- Store copied icons in a small app-owned asset folder.
- Maintain an icon registry mapping app usage to the copied asset.
- Keep icon dimensions stable so hover, disabled, and loading states do not
  resize controls.

## Forbidden

- Full icon archive committed to repo.
- Full extracted `PNGs`, `SVGs`, or font dump committed to repo.
- Private absolute source paths in repo artifacts.
- Remote icon dependency.
- Handmade replacement icons when a matching package icon exists.

## Logo Rule

The owner-supplied logo asset is locked.

Allowed:

- scale
- spacing
- optical centering

Forbidden:

- redraw
- recolor
- simplify
- replace

## Resume From Here

Use this policy in `UI_FINAL_DESIGN_SYSTEM_REBASE` before adding any new icon
assets.
