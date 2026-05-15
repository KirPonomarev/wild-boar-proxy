# Root Cause Report

## Reproduced Failure

Against the local live server, `?screen=overview&source=live` initially
displayed:

- `sourcePicker = live`
- `.desktop.dataset.source = fixture`
- `brandCaption = "демо-просмотр UI"`
- fixture-style placeholder values for mode, endpoint, and pool counts

That reproduced both on initial load and after switching the picker from
fixture to live with a short wait.

## Localized Cause

The failure was a UI handoff defect, not a runtime or live-packet defect.

Facts:

1. The root `.desktop` starts in HTML as `data-source="fixture"`.
2. `setLiveReadonly()` was async and did not mark the screen as live before the
   fetch resolved.
3. `overview` used the generic `loadLiveReadonly() -> renderSnapshot()` path, so
   the DOM kept its fixture/demo shell while the live fetch was in flight.
4. A longer wait showed that the final live packet did eventually render
   correctly, which ruled out a steady-state command/live contradiction.

## Repair

The repair stays in the UI binding layer:

- prime the screen into `source=live` immediately when `setLiveReadonly()` starts;
- set an honest pending live caption and source footer;
- on `overview`, replace fixture placeholders with an explicit loading state
  while the live fetch is unresolved.

## Why This Is Canonical

- no runtime truth code changed;
- no command adapter or allowlist changes were needed;
- no mutation surfaces were activated;
- pending UI no longer overclaims fixture/demo truth while live source is active.
