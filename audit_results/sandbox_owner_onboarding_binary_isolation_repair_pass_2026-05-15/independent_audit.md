# Independent Audit

## Scope

Decide whether the repaired sandbox owner onboarding lane is now admissible for a rerun of `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`.

## Evidence reviewed

- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/sandbox_owner_helpers.py`
- `/Volumes/Work/wild-boar-proxy/tests/test_cli.py`
- `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/owner_lane_path_matrix.json`
- `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/sandbox_owner_lane_verification.json`
- `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/installer_idempotence_check.json`
- `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_owner_onboarding_binary_isolation_repair_pass_2026-05-15/targeted_test_report.txt`

## Findings

1. `installer init --json` now materializes the sandbox owner helper chain under `/Users/kirillponomarev/.codex-custom-test/managed/bin/` plus `/Users/kirillponomarev/.codex-custom-test/managed/supervisor-sync.sh`.
2. The materialized helper files are executable, carry repo-managed markers, and their contents do not include `.codex-custom-cli` or `.cli-proxy-api`.
3. A second installer pass returned `changed_files = []`, which confirms the helper chain is recognized and idempotent rather than rewritten on every run.
4. The repo-owned helper wrappers dispatch to `wild_boar_proxy.sandbox_owner_helpers`, which reads sandbox runtime paths from `WBP_*` env surfaces instead of hardcoded live home paths.
5. The targeted test suite passed and includes direct proof that installer-materialized helper scripts can import an explicit auth ref into `reserve` and pass `accounts validate` in an isolated temp env.

## Remaining risks

- This repair contour did not rerun the shared sandbox onboarding mutation contour itself; it only restored the admissible owner lane.
- Runtime failure branches for ambiguous selection, reserve-first violation, validate failure, sync failure, or status failure still remain valid and must be checked in the onboarding rerun contour.

## Verdict

`GO`

## Rationale

The owner onboarding lane is now materialized inside sandbox-local paths, is free of hardcoded live home-path dependencies, and has both live materialization proof and targeted temp-env command proof, which is enough to honestly rerun `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`.
