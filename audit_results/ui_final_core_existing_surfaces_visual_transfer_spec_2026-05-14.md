# UI_FINAL_CORE_EXISTING_SURFACES_VISUAL_TRANSFER Spec

Date: 2026-05-14

## Goal

Transfer the final visual baseline onto the already admitted web design UI
surfaces without expanding product behavior, command surfaces, runtime truth, or
desktop scope.

## Canon Boundary

- UI remains a renderer prototype for desktop admission review.
- Browser payloads remain limited to `ui_action` plus bounded structured fields.
- Runtime truth is still supplied only by strict JSON command/read-only surfaces.
- This contour does not admit new screens, new actions, new command adapter specs,
  new live server actions, or new backend behavior.

## Changed Surfaces

- `overview`: header action geometry, table/card rhythm inherited through CSS.
- `accounts`: table/card density and action button containment.
- `diagnostics`: signal-detail geometry and chart block sizing.
- `settings`: existing readonly settings surface refit into a hub layout while
  preserving the same observed fields and the same safe action buttons.
- existing confirmation/onboard modal styling remained on the locked modal tokens.

## Explicit Non-Goals

- No desktop implementation.
- No runtime behavior change.
- No command adapter or live server allowlist change.
- No new `ui_action`.
- No route editor implementation.
- No API key, token, path, raw JSON, or provider configuration input.
- No direct reads of config, route, state, secret, evidence, or log files.

## Identity Preservation Check

The visual transfer keeps the existing Wild Boar identity direction: sidebar,
brand mark treatment, warm paper surfaces, compact operator copy, restrained
status chips, and structured operational tables. Any outside pattern thinking is
non-attributed background only and is not repo evidence.

## Resume From Here

Run the full verification set, record browser smoke facts, complete independent
audit, then close with a single scoped commit if all checks pass.
