# Spec: Audit Trail Metadata Correction For Desktop Slice

## Objective

Correct stale git/integration metadata in the closed desktop-launch slice artifacts after commit `02d18ad9` and push, without changing any runtime, UI, test, or product-status truth.

## In Scope

- update the desktop-launch slice closeout Git section to match actual commit/push truth
- update the desktop-launch slice independent audit note so it no longer claims the slice is uncommitted
- add a correction summary artifact for the metadata pass
- add a closeout for this metadata correction pass

## Out of Scope

- runtime code changes
- UI changes
- test changes
- external API route work
- product status upgrades
- new runtime/browser evidence

## Constraints

- `8B` must remain `partial_blocked`
- `EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING` must remain the active external blocker
- only metadata/evidence truth may change

## Assumptions

- commit `02d18ad9` remains the desktop-launch slice integration commit
- branch `codex/external-agent-lab-isolated` remains pushed to origin

## Acceptance Criteria

- [x] desktop-launch slice closeout Git section reflects `commit=02d18ad9` and `pushed=yes`
- [x] independent audit no longer claims the slice is uncommitted
- [x] correction pass explicitly preserves `8B = partial_blocked`
- [x] correction pass explicitly preserves `EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING`
- [x] runtime/product files remain untouched

## Verification

- tests:
  - none; metadata-only pass
- build:
  - `git diff --check`
- manual:
  - `git show --stat 02d18ad9`
  - compare updated closeout/audit artifacts against current git truth
- live evidence:
  - `correction_summary.json`

## Open Questions

- none
