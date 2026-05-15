# TECH_GATE_AND_ENV_INVENTORY_PASS Risk Matrix

## High

- `POST /api/action` is already exposed by the live server.
  - Risk: a sloppy next contour could accidentally leave readonly scope and
    dispatch mutations.
  - Guard: `WEB_LIVE_SERVER_READONLY_ADMISSION_PASS` must be GET-only and must
    explicitly forbid action dispatch.

- 13 canon-required commands are not wired through the current adapter surface.
  - Risk: doc presence could be mistaken for executable availability.
  - Guard: every future contour must distinguish `canon-required` from
    `repo-wired` and `runtime-proven`.

## Medium

- `launch_client_dispatch` is UI-admitted only through a server-owned bounded
  path, not a browser path.
  - Risk: next contours could incorrectly assume generic launch availability.
  - Guard: keep launch admission conditional on bounded server-owned path.

- Account and route actions are visible in metadata before any sandbox contour.
  - Risk: operators may read availability as permission to execute.
  - Guard: no mutation contour before sandbox boundary and owner approval.

- `stable_repair_apply` exists in the adapter but is intentionally absent from
  the UI allowlist.
  - Risk: repo readers may overestimate readiness of recovery apply.
  - Guard: treat as deferred until a dedicated contour explicitly admits it.

## Low

- Git hooks are configured, but hook presence is a local hygiene fact rather
  than runtime truth.
  - Risk: over-reading workflow hygiene as product readiness.
  - Guard: keep hooks observation separate from runtime/readiness decisions.

- `api/actions` metadata exposes availability and confirmation rules, but not
  runtime proof.
  - Risk: metadata could be mistaken for live health or proof.
  - Guard: require command packet plus refresh proof for all truth claims.
