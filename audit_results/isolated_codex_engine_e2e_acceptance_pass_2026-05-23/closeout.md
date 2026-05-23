# ISOLATED_CODEX_ENGINE_E2E_ACCEPTANCE_PASS Closeout

## Goal

Prove the practical execution-core finish through an isolated headless Codex
engine process using WBP, without patching Codex, mutating the current operator
profile, or claiming GUI Desktop E2E success.

## Result

- status: `closed_success_engine_acceptance`
- final verdict: isolated headless Codex engine returned exact `OK` through the
  WBP endpoint with isolated `CODEX_HOME`; strict replay with isolated `HOME`
  also passed, WBP stayed healthy, and the prior GUI Desktop boundary remains
  intact
- next action: owner may either accept
  `EXECUTION_CORE_REPAIR_CLOSED_AND_ENGINE_ACCEPTANCE_READY` as the practical
  program close or explicitly open `CODEX_DESKTOP_HOST_SURFACE_INVESTIGATION_PASS`
  if GUI Desktop proof remains mandatory

## Contour Capsule

- goal: prove isolated headless Codex engine E2E acceptance through WBP without
  claiming GUI Desktop success
- branch: `codex/external-agent-lab-isolated`
- head: `74310e6`
- touched files:
  - `audit_results/isolated_codex_app_e2e_pass_2026-05-23/closeout.md`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/spec.md`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/baseline.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/proof.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/metrics.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/redaction_audit.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/independent_audit.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/closeout.md`
- tests run:
  - live `codex exec --json` with isolated `CODEX_HOME`
  - live `codex exec --json` with isolated `HOME` and isolated `CODEX_HOME`
  - WBP pre/post `status --json`
  - WBP pre/post `healthcheck --json`
  - WBP pre/post `external-models status --json`
  - WBP pre `external-models check --route wbp-deepseek-v3 --json`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - full `~/.codex` metadata is noisy while the live operator Codex is running;
    sensitive `~/.codex/auth.json` and `~/.codex/config.toml` were checked
    separately and stayed unchanged
  - external subagent audit was unavailable because the session hit the agent
    thread limit; packet uses local replay audit instead
- next exact command: `git push origin codex/external-agent-lab-isolated`

## Verification

- tests:
  - no repo code patch was required; live command proofs were the primary tests
- build:
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - verified exact `OK` agent message in JSONL output
  - verified token usage packets
  - verified strict replay with both `HOME` and `CODEX_HOME` isolated
  - verified no GUI Desktop success claim is made
- live verification:
  - WBP preflight `status`, `healthcheck`, `accounts list`,
    `external-models status`, `external-models check`
  - isolated engine smoke
  - strict isolated home replay
  - WBP post-smoke `status`, `healthcheck`, `external-models status`

## Artifacts

- spec:
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/spec.md`
- packet:
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/baseline.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/proof.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/metrics.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/redaction_audit.json`
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/independent_audit.json`
- report:
  - `audit_results/isolated_codex_engine_e2e_acceptance_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: no

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; temporary auth copies were created only under
  `/tmp` and removed before closeout

## Notes

- blockers encountered:
  - full `~/.codex` before/after metadata changed because the live operator
    Codex writes sqlite/cache surfaces while running; this was classified as
    ambient current-app activity, not engine mutation, and narrowed to sensitive
    profile surfaces for proof
- follow-up contour:
  - program completion reconciliation if owner accepts engine acceptance as the
    practical final path
  - `CODEX_DESKTOP_HOST_SURFACE_INVESTIGATION_PASS` only if GUI Desktop proof
    remains mandatory
- resume from here: `Owner decision required: accept EXECUTION_CORE_REPAIR_CLOSED_AND_ENGINE_ACCEPTANCE_READY as practical completion, or explicitly open Codex Desktop host-surface investigation`
