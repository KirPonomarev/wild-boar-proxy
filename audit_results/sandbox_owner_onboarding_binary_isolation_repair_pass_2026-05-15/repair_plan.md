# Repair Plan

## Blocker

The previous onboarding contour stopped before mutation because sandbox-local owner helper surfaces were absent and the only available external helpers were hardwired to live home paths.

## Minimal repair chosen

1. Keep the existing owner command surface intact.
2. Extend `installer init --json` so it materializes a repo-owned helper chain inside sandbox-local managed paths.
3. Make those helpers thin wrappers to repo code rather than live binaries.
4. Keep helper logic on `WBP_*` runtime paths so sandbox truth remains explicit.

## Why this path won

- It reuses the existing installer materialization contour instead of creating a new bootstrap surface.
- It avoids live-binary fallback.
- It keeps the repair on isolation/materialization rather than changing onboarding semantics.
- It gives us a helper chain that can also support follow-on account contours.
