# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS Closeout

## Goal

Rerun sandbox onboarding after owner-lane isolation repair and prove reserve-first admission through `accounts onboard --json` plus post-command refresh, without work-contour drift or UI overclaim.

## Result

- status: completed with blocker
- final verdict: STOP_AND_DIAGNOSE
- next action: run `SANDBOX_AUTH_PAYLOAD_COMPATIBILITY_REPAIR_PASS`, then rerun `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`

## Contour Capsule

- goal: verify that repaired sandbox owner helpers can carry a real reserve-first onboarding packet to post-refresh proof
- branch: `codex/external-agent-lab-isolated`
- head: `4d84280 Repair sandbox owner onboarding helper lane`
- touched files: `audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/*`
- tests run: sandbox `accounts list --json` pre-refresh capture; sandbox `accounts onboard --json --auth-ref /Users/kirillponomarev/.codex-custom-test/auth.json --non-interactive`; sandbox `accounts list --json` post-refresh capture; forbidden live-path snapshot diff; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/closeout.md`; independent audit
- blocked risks: reserve-first semantics were never reached because the sandbox auth payload shape does not satisfy the repaired owner-helper auth contract; rerunning onboarding again without auth-contract repair would only repeat the same non-mutating failure
- next exact command: `python3 - <<'PY'\nimport json\nfrom pathlib import Path\nprint(json.dumps(json.loads(Path('/Users/kirillponomarev/.codex-custom-test/auth.json').read_text()), indent=2))\nPY`

## Verification

- tests: command packet and refresh packet are captured in `onboard_command_packet.json` and `post_onboard_accounts_packet.json`; forbidden drift check is captured in `forbidden_drift_check.json`
- build: not applicable
- manual: confirmed the rerun used repaired sandbox helpers, returned `ONBOARD_FAILED`, emitted stderr `invalid auth type: None`, and left the sandbox registry empty
- live verification: forbidden live paths under `/Users/kirillponomarev/.codex-custom-cli/**` and `/Users/kirillponomarev/.cli-proxy-api/config.yaml` remained unchanged; `changed_files` stayed empty

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/pre_onboard_snapshot.json`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; the audit captures auth payload shape and keys, but does not copy live work-contour auth/config data

## Notes

- blockers encountered: `accounts onboard --json` reached the repaired helper lane but failed before reserve-first semantics because `/Users/kirillponomarev/.codex-custom-test/auth.json` has `auth_mode` plus `OPENAI_API_KEY`, while the helper validator expects `type in {"codex","apikey"}`
- follow-up contour: `SANDBOX_AUTH_PAYLOAD_COMPATIBILITY_REPAIR_PASS`
- resume from here: `SANDBOX_AUTH_PAYLOAD_COMPATIBILITY_REPAIR_PASS`
