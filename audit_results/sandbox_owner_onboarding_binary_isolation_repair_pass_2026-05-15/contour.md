# SANDBOX_OWNER_ONBOARDING_BINARY_ISOLATION_REPAIR_PASS

## Goal

Repair the missing and unsafe sandbox owner onboarding lane so that `accounts onboard --json` can resolve sandbox-local owner helpers instead of stopping at `MISSING_ONBOARD_BIN` or falling back to live home-path binaries.

## Result

`GO_TO_RERUN_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`

## What changed

- `installer init --json` now materializes a repo-owned sandbox helper chain:
  - `managed/bin/codex-accounts`
  - `managed/bin/codex-account-onboard`
  - `managed/bin/codex-managed-status`
  - `managed/supervisor-sync.sh`
- The materialized helpers are wrappers to `wild_boar_proxy.sandbox_owner_helpers`.
- The wrappers carry repo-managed markers and no hardcoded `~/.codex-custom-cli` or `~/.cli-proxy-api` strings.
- The sandbox helper module reads runtime paths from `WBP_*` env surfaces.

## Why this is enough

The repair contour only had to prove owner-lane admissibility. It did not need to perform the real onboarding mutation in the shared sandbox. That proof now exists through:

- sandbox-local helper materialization
- zero live-path drift
- zero unsafe live-path strings in helper contents
- idempotent second `installer init --json`
- targeted temp-env tests proving explicit-auth onboarding helper flow
