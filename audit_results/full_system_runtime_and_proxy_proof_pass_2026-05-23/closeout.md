# FULL_SYSTEM_RUNTIME_AND_PROXY_PROOF_PASS Closeout

## Goal

Prove that the managed runtime and CLIProxy-backed proxy path stay truthful and
usable under bounded load, while preserving 25-account registry truth and
keeping the current working Codex untouched.

## Result

- status: `closed_success`
- final verdict: fresh preflight passed; owner-path smoke passed; bounded proxy
  load passed `20/20` at concurrency `3`; post-load reclear stayed green
- next action: proceed to `DEEPSEEK_DIRECT_API_MINIMAL_TOKEN_PROOF_PASS`

## Contour Capsule

- goal: runtime/proxy truth, bounded load, and post-load reclear without
  false-green
- branch: `codex/external-agent-lab-isolated`
- head: `98505eb`
- touched files:
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/spec.md`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/baseline.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/proxy_smoke.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/load_metrics.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/metrics.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/post_load_reclear.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/proof.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/redaction_audit.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/independent_audit.json`
  - `audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/closeout.md`
- tests run:
  - `python3 -B -m unittest tests.test_cli.CliTests.test_healthcheck_responses_probe_emits_x_session_id tests.test_cli.CliTests.test_launch_smoke_reports_stable_runtime_consumer_contract tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_sync_materializes_selected_backend_snapshot_on_success tests.test_cli.CliTests.test_sync_refreshes_selected_backend_snapshot_observed_at_on_success -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- blocked risks:
  - owner-lane concurrent `launch smoke --json` serializes via `LOCK_HELD`; this
    is classified as lock guardrail behavior, not proxy failure
  - stable policy drift remains an explicit claim boundary; no
    `stable-15-proved` or `active-only-traffic` claim is made here
- next exact command:
  - `python3 -m wild_boar_proxy external-models check --route wbp-deepseek-v3 --json`

## Verification

- tests:
  - targeted runtime/proxy owner-surface tests passed (`6` tests)
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - verified `sync -> rollout rotation inspect -> launch smoke`
  - verified bounded proxy `/responses` load through runtime helper transport
  - verified post-load `sync/status/healthcheck/accounts/rotation`
- live verification:
  - owner smoke: passed
  - bounded proxy load: `20/20` passed at concurrency `3`
  - post-load reclear: `status`, `healthcheck`, and `rotation inspect` all OK

## Artifacts

- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/spec.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/baseline.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/proxy_smoke.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/load_metrics.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/metrics.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/post_load_reclear.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/proof.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/redaction_audit.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/independent_audit.json`
- report:
  - `/Volumes/Work/wild-boar-proxy/audit_results/full_system_runtime_and_proxy_proof_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `98505eb`
- pushed: `no`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes`; artifact scans found no raw key material

## Notes

- blockers encountered:
  - stale rotation evidence before `sync --json`; resolved through the owner
    path and reverified as `participation_evidence_available`
  - concurrent owner smoke returned `LOCK_HELD`; classified as owner-lane
    serialization, not proxy/load failure
  - a local `urllib` probe without runtime helper transport returned `503`; the
    canonical helper transport passed `20/20`
- follow-up contour:
  - `DEEPSEEK_DIRECT_API_MINIMAL_TOKEN_PROOF_PASS`
- resume from here: `DEEPSEEK_DIRECT_API_MINIMAL_TOKEN_PROOF_PASS`
