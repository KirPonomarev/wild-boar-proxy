# Independent Audit

## Scope

Resolve whether `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS` can continue honestly with the currently materialized sandbox onboarding lane.

## Evidence reviewed

- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
- `/Users/kirillponomarev/.codex-custom-cli/managed/bin/codex-account-onboard`
- `/Users/kirillponomarev/.codex-custom-cli/managed/bin/codex-accounts`
- `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/pre_onboard_snapshot.json`
- `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_2026-05-15/onboard_command_packet.json`
- `/Volumes/Work/wild-boar-proxy/CANON.md`
- `/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md`
- `/Volumes/Work/wild-boar-proxy/COMMAND_API.md`
- `/Volumes/Work/wild-boar-proxy/AGENTS.md`

## Findings

1. `RuntimePaths.from_env` expects the onboarding owner lane to be redirectable through sandbox-local `WBP_*` paths, including `onboard_bin` and `accounts_bin`.
2. The current sandbox snapshot does not contain the required owner executables or `supervisor-sync.sh`.
3. The actual onboarding command packet already stops at `MISSING_ONBOARD_BIN` before any mutation and reports `changed_files = []`.
4. The only available real owner binaries are the live ones under `/Users/kirillponomarev/.codex-custom-cli/managed/bin/`.
5. Those binaries hardcode `Path.home()`, `~/.codex-custom-cli`, and `~/.cli-proxy-api`; they are not sandboxed by `WBP_*` and would target the work contour if invoked.

## Contradiction resolution

One mini-audit returned `GO` by observing that `run_onboard()` itself does not contain an explicit work-contour fallback branch. That reading is incomplete. The absence of a fallback branch in the wrapper does not make the external binary sandbox-safe. The decisive truth is the combination of:

- current packet: `MISSING_ONBOARD_BIN`
- missing sandbox owner binaries
- live owner binaries hardwired to work paths

That combination makes the contour non-admissible for honest sandbox onboarding.

## Verdict

`STOP_AND_DIAGNOSE`

## Rationale

The sandbox owner onboarding path is not materialized, and the only available substitute binaries would violate sandbox isolation by reading and writing the live work contour.
