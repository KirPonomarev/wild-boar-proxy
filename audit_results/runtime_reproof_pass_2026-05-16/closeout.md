# RUNTIME_REPROOF_PASS Closeout

## Goal

Reprove stable runtime truth after approved-target family repair and determine
whether that live evidence is enough to reopen exact auth-source admission for
the sandbox onboarding chain.

## Result

- status: `completed`
- final verdict: `GO_TO_SELECTOR_REFRESH_OWNER_PATH_PASS`
- next action: refresh owner-path participation evidence now that runtime truth
  is aligned to the approved target, before reopening exact auth-source
  admission

## Contour Capsule

- goal: settle desired/effective runtime truth with owner-path live evidence,
  then judge whether exact auth-source admission is now honestly earned
- branch: `codex/external-agent-lab-isolated`
- head: `a884b20 Repair stable policy source target family`
- touched files:
  - `audit_results/runtime_reproof_pass_2026-05-16/*`
- tests run:
  - `python3 -m wild_boar_proxy healthcheck --json`
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy launch smoke --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m unittest -q tests.test_cli.CliTests.test_launch_smoke_activates_approved_target_via_generated_config_and_status_reports_effective_target tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/runtime_reproof_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - rotation selector surface remains stale
  - exact auth-source selection remains family-level rather than singleton
  - sandbox auth materialization remains unearned
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - healthcheck alone kept runtime truth split and did not settle activation
  - launch smoke activated approved target and status reported effective target
  - rotation inspect still reports stale selected snapshot separately from
    cleared policy drift
- build:
  - `git diff --check`
- manual:
  - `healthcheck --json` returned `OK`, `healthy`, and `ready`, but left
    `status --json` at `approved_target_selected` vs `observed_source_active`
  - `launch smoke --json` returned `OK` and wrote only:
    `/Users/kirillponomarev/.codex-custom-cli/config.toml`,
    `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`,
    `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`,
    `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
  - post-smoke `status --json` reported:
    `effective_source_status = approved_target_active_by_activation_evidence`,
    `claim_gate = clear`,
    `policy_drift = clear`,
    `snapshot_activation_outcome = approved_target_activated`
  - post-smoke `rollout rotation inspect --json` still reported
    `ROTATION_EVIDENCE_STALE` with stale selected-backend family count `9`
- live verification:
  - runtime activation was reproved live through canon-supported owner surfaces
  - exact auth-source admission still remains deferred until selector freshness
    is restored

## Artifacts

- spec:
  - `audit_results/runtime_reproof_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/runtime_reproof_pass_2026-05-16/runtime_basis.json`
  - `audit_results/runtime_reproof_pass_2026-05-16/owner_path_reproof_packets.json`
  - `audit_results/runtime_reproof_pass_2026-05-16/runtime_truth_classification.json`
  - `audit_results/runtime_reproof_pass_2026-05-16/claim_gate_evaluation.json`
  - `audit_results/runtime_reproof_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/runtime_reproof_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only machine-readable owner packets,
  selected backend ids, exact target basenames, and bounded path surfaces were
  recorded`

## Notes

- blockers encountered:
  - healthcheck alone was insufficient to settle effective stable runtime truth
  - launch smoke settled runtime truth but did not collapse the effective
    approved-target family to one exact auth source
  - rotation participation evidence remains stale even after successful runtime
    activation
- follow-up contour:
  - `SELECTOR_REFRESH_OWNER_PATH_PASS`
- resume from here: `refresh selected-backend participation evidence through the owner path before reopening exact auth-source admission`
