# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS

## Goal

Prove reserve-first sandbox onboarding through `accounts onboard --json` without leaving `/Users/kirillponomarev/.codex-custom-test` and without overclaiming success before packet-plus-refresh evidence.

## Outcome

`STOP_AND_DIAGNOSE`

## Decisive blocker

The sandbox-local owner onboarding lane is not fully materialized:

- `/Users/kirillponomarev/.codex-custom-test/managed/bin/codex-account-onboard` is missing
- `/Users/kirillponomarev/.codex-custom-test/managed/bin/codex-accounts` is missing
- `/Users/kirillponomarev/.codex-custom-test/managed/bin/codex-managed-status` is missing
- `/Users/kirillponomarev/.codex-custom-test/managed/supervisor-sync.sh` is missing

The current owner packet proves the blocker directly:

- `machine_error_code = MISSING_ONBOARD_BIN`
- `changed_files = []`

The only existing external owner binaries live under `/Users/kirillponomarev/.codex-custom-cli/managed/bin/` and are hardwired to `Path.home()` plus `~/.codex-custom-cli` and `~/.cli-proxy-api`, so using them would break sandbox isolation.

## Next honest move

Run a dedicated stop-and-diagnose repair contour to materialize sandbox-safe onboarding owner binaries and post-proof helpers before rerunning `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`.
