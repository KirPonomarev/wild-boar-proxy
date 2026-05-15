# STABLE_POLICY_SOURCE_REPAIR_PASS Closeout

## Goal

Repair the approved control-owned target inventory to match the current
owner-path policy/source-copy family, then verify that target-family alignment
and runtime-consumer alignment remain separate truth surfaces.

## Result

- status: `completed`
- final verdict: `GO_TO_RUNTIME_REPROOF_PASS`
- next action: refresh live runtime truth against the newly aligned approved
  target family without reopening selector or exact-source admission

## Contour Capsule

- goal: close the family-level approved target drift by using only
  `stable repair --apply --json` and then decide the next truth gap honestly
- branch: `codex/external-agent-lab-isolated`
- head: `c56437a Reconcile stable policy source family truth`
- touched files:
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/*`
- tests run:
  - `python3 -m wild_boar_proxy stable repair --dry-run --json`
  - `python3 -m wild_boar_proxy stable repair --apply --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_contradicted_for_policy_drift tests.test_cli.CliTests.test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready tests.test_cli.CliTests.test_stable_repair_dry_run_reports_materialized_approved_target_after_apply`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/stable_policy_source_repair_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - runtime-consumer truth still reports `activation_pending`
  - effective runtime source remains `observed_stable_inventory_source`
  - exact-source admission remains unearned
- next exact command: `python3 -m wild_boar_proxy healthcheck --json`

## Verification

- tests:
  - owner-path repair apply succeeded with `STABLE_REPAIR_APPLIED`
  - post-apply dry-run reported `approved_repair_target_reference.status = materialized_aligned`
  - post-repair rotation inspect reported `policy_drift_status = clear`
  - post-repair status reported desired source `approved_repair_target`,
    effective source `observed_stable_inventory_source`, and
    `activation_pending`
- build:
  - `git diff --check`
- manual:
  - pre-repair delta was add `k-gpt-pro`, `new-new55555`,
    `kp8750410-team`; prune `codex-k.gpt.pro.3k@outlook.com-free.json`
  - approved target inventory count moved from `9` to `11`
  - apply changed files stayed under
    `/Users/kirillponomarev/.codex-custom-cli/managed/stable-repair-target/`
  - no `.stable-repair-stage-*` or `.stable-repair-backup-*` paths remained
    after successful apply
  - no sandbox `auth.json` write occurred
- live verification:
  - not performed in this contour; runtime activation proof is deferred to
    `RUNTIME_REPROOF_PASS`

## Artifacts

- spec:
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/repair_basis.json`
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/repair_apply_packet.json`
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/post_repair_family_verification.json`
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/changed_files_scope.json`
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/rollback_verification.json`
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/stable_policy_source_repair_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only machine-readable owner packets, exact
  target basenames, and bounded path surfaces were recorded`

## Notes

- blockers encountered:
  - post-apply dry-run returned `LOCK_HELD`, but still emitted a complete
    transaction plan showing `materialized_aligned` and zero remaining delta
  - runtime truth remains behind family repair truth and still needs live
    reproof
- follow-up contour:
  - `RUNTIME_REPROOF_PASS`
- resume from here: `run healthcheck --json first in RUNTIME_REPROOF_PASS to refresh live runtime truth against the repaired approved target family`
