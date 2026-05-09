<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Desktop HTML Renderer Decision

## Contour

`UI_DESKTOP_HTML_RENDERER_ADMISSION_AND_PASSPORTS`

## Decision

The desktop HTML renderer lane is admitted as a local desktop companion UI
direction, not as a public web product.

`pywebview` is selected as the first implementation-spike target because it is
the cheapest likely path for embedding local HTML/CSS inside a desktop app while
keeping the Python control-layer ecosystem close to the existing repository.

This is not a final packaging dependency lock. The next implementation contour
must prove `pywebview` in a local spike before live command wiring or broader UI
work begins.

## Evidence

- The render package contains static HTML/CSS screens, PNG baselines, and one
  local asset.
- Representative HTML has inline CSS, no script tags, and no external CDN
  references.
- PNG baselines are fixed at `3200x2000`, matching a `1600x1000` logical design
  viewport at 2x scale.
- `boar_mark.png` is available as a local asset.
- Current Python environment does not already provide `webview`, `PySide6`,
  `PyQt6`, or `cefpython3`.
- Current local toolchain exposes `node` and `npm`, but no installed `electron`,
  `cargo`, `tauri`, or `tauri` CLI was detected.

## Candidate Assessment

| Candidate | Status | Notes |
| --- | --- | --- |
| `pywebview` | First spike target | Smallest likely desktop wrapper for local HTML/CSS. Keeps implementation close to Python. Needs dependency-backed proof in the next contour. |
| `PySide6 / Qt WebEngine` | Fallback candidate | Strong renderer, but heavier dependency and larger packaging surface. Use only if `pywebview` cannot preserve the design or app integration needs. |
| `Electron` | Deferred fallback | High visual confidence, but larger runtime footprint and more packaging weight. Avoid unless lighter desktop renderers fail. |
| `Tauri` | Deferred fallback | Good desktop architecture, but adds Rust/toolchain and packaging decisions that are premature here. |

## Dependency Policy

No renderer dependency was installed in this contour.

Any future dependency installation must be scoped to the renderer spike, recorded
in the contour packet, and must not introduce runtime truth, command semantics,
or direct state/log access.

## Boundary

The renderer may own presentation, local layout, fixture rendering, and visual
parity work. It must not own runtime truth, command meaning, recovery truth, or
account lifecycle semantics.

`ui_shell.py` remains the fallback/control baseline.

## Next

Open `UI_DESKTOP_HTML_STATIC_OVERVIEW_WITH_FIXTURES`.

The first coding contour should prove:

- `pywebview` can host the local overview HTML shell;
- `boar_mark.png` and local CSS render correctly;
- the overview screen can render from JSON fixtures;
- no live command wiring is present yet.
