# SANDBOX_AUTH_PAYLOAD_COMPATIBILITY_REPAIR_PASS Closeout

## Goal

Repair sandbox auth payload compatibility with the sandbox owner onboarding lane so the next onboarding rerun reaches reserve-first evaluation instead of stopping at auth-type mismatch.

## Result

- status: completed
- final verdict: GO_TO_RERUN_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS
- next action: rerun `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`

## Contour Capsule

- goal: make the current sandbox auth payload admissible to the repaired sandbox owner helper lane without changing onboarding semantics
- branch: `codex/external-agent-lab-isolated`
- head: `4e92c61 Audit sandbox onboarding rerun auth blocker`
- touched files: `wild_boar_proxy/sandbox_owner_helpers.py`; `tests/test_cli.py`; `audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/*`
- tests run: `python3 -m py_compile wild_boar_proxy/sandbox_owner_helpers.py tests/test_cli.py`; 6 targeted CLI tests covering explicit auth onboarding, legacy `auth_mode=apikey` compatibility, invalid legacy payload failure, and onboarding reserve-first regressions; live read-only admissibility proof on `/Users/kirillponomarev/.codex-custom-test/auth.json`; forbidden live-path drift comparison; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: this contour does not prove reserve-first success; it only removes the auth-type mismatch blocker before the onboarding rerun
- next exact command: `env WBP_PROFILE_DIR=/Users/kirillponomarev/.codex-custom-test WBP_AUTH_FILE=/Users/kirillponomarev/.codex-custom-test/auth.json WBP_MANAGED_DIR=/Users/kirillponomarev/.codex-custom-test/managed WBP_STABLE_CONFIG=/Users/kirillponomarev/.codex-custom-test/stable/config.yaml WBP_CONFIG_TOML=/Users/kirillponomarev/.codex-custom-test/config.toml WBP_RUNTIME_MODE_FILE=/Users/kirillponomarev/.codex-custom-test/runtime-mode.txt WBP_RUNTIME_EFFECTIVE_MODE_FILE=/Users/kirillponomarev/.codex-custom-test/runtime-effective-mode.txt WBP_REGISTRY_FILE=/Users/kirillponomarev/.codex-custom-test/managed/backend-registry.json WBP_STATE_FILE=/Users/kirillponomarev/.codex-custom-test/managed/supervisor-state.json WBP_MANAGED_CONFIG_FILE=/Users/kirillponomarev/.codex-custom-test/managed/managed-config.yaml WBP_LAUNCHER_SCRIPT=/Users/kirillponomarev/.codex-custom-test/codex-custom-launch.sh WBP_EXTERNAL_MODELS_DIR=/Users/kirillponomarev/.codex-custom-test/external-models python3 -m wild_boar_proxy accounts onboard --json --auth-ref /Users/kirillponomarev/.codex-custom-test/auth.json --non-interactive`

## Verification

- tests: targeted helper-lane tests passed; invalid legacy payload still fails honestly
- build: `py_compile` passed for the touched Python files
- manual: live read-only proof on `/Users/kirillponomarev/.codex-custom-test/auth.json` now normalizes the payload to `apikey` without mutating the file
- live verification: forbidden live paths remain unchanged relative to the previous onboarding rerun snapshot

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/compatibility_verification.json`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; compatibility proof uses sandbox auth shape and key presence only, with no live auth inventory mutation or work-contour fallback

## Notes

- blockers encountered: none after narrowing the repair to auth-kind normalization in the sandbox owner helper boundary
- follow-up contour: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
- resume from here: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
