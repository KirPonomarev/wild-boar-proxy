# ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS Closeout

## Goal

Rerun the sandbox lifecycle matrix after stage-10 policy admission and prove
canonical lifecycle actions starting from `accounts promote auth --json`.

## Result

- status: `STOP_AND_DIAGNOSE`
- final verdict: promote passed policy/validate/sync but failed verified
  post-promotion status attestation and rolled back cleanly
- next action: open `SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS`

## Contour Capsule

- goal: rerun lifecycle proof after stage-10 sandbox policy admission
- branch: `codex/external-agent-lab-isolated`
- head: `01be4f8 Audit sandbox policy stage 10 admission`
- touched files:
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/preflight_snapshot.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/pre_promote_accounts.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/promote_packet.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/post_promote_accounts.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/post_promote_status.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/post_action_matrix.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/rollback_verification.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/forbidden_drift_check.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/decision_packet.json`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/contour.md`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/independent_audit.md`,
  `audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/closeout.md`
- tests run:
  `python3 -m wild_boar_proxy accounts promote auth --json` under sandbox env,
  post-promote `accounts list --json`,
  post-promote `status --json`,
  forbidden live-path hash comparison,
  `git diff --check`,
  `python3 tools/check_closeout_resilience.py audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/closeout.md`,
  `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  active-lane runtime attestation still fails with `HTTP 401 Invalid API key`
- next exact command:
  `python3 -m wild_boar_proxy status --json` under the sandbox env map inside
  `SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS`

## Verification

- tests:
  real sandbox owner packet for promote plus paired post-refresh/status readout
- build:
  not applicable; no runtime code changed in this contour
- manual:
  confirmed rollback restored backend to `reserve/manual_hold=false`
- live verification:
  promote packet reported `PROMOTION_STATUS_FAILED` with rollback completed and
  post-status packet reported `ATTESTATION_FAILED`

## Artifacts

- spec:
  `/Volumes/Work/wild-boar-proxy/audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/contour.md`
- packet:
  `/Volumes/Work/wild-boar-proxy/audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/promote_packet.json`
- report:
  `/Volumes/Work/wild-boar-proxy/audit_results/account_lifecycle_sandbox_actions_pass_rerun_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts record packet/path truth and
  error class, not secret values

## Notes

- blockers encountered:
  `PROMOTION_STATUS_FAILED` after status proof, with nested
  `ATTESTATION_FAILED` and `HTTP 401 Invalid API key`
- follow-up contour:
  `SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS`
- resume from here:
  `SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS`
