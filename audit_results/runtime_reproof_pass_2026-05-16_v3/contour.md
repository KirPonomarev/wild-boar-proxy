CONTOUR:
Goal: reprove effective stable runtime consumer truth after the sync-managed write-seam repair and determine whether exact auth-source admission is now honestly earned
Size: M
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- owner-path runtime reproof via `healthcheck --json` and `launch smoke --json`
- post-reproof `status --json` and `rollout rotation inspect --json`
- targeted runtime/rotation tests
- independent audit on factual packets

Out of scope:
- sandbox `auth.json` materialization
- onboarding rerun
- exact auth-source admission implementation itself
- selector refresh repeat
- code changes unrelated to runtime reproof

Assumptions:
- sync-managed write seam repair is already closed and selector evidence is fresh
- live runtime observation is required before desired source can become effective truth

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_cli.py`
- runtime evidence:
  - `audit_results/sync_managed_mode_write_surface_repair_pass_2026-05-16/*`
  - live `healthcheck --json`
  - live `launch smoke --json`
  - live `status --json`
  - live `rollout rotation inspect --json`

Commands / files:
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy launch smoke --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m unittest -q tests.test_cli.CliTests.test_launch_smoke_activates_approved_target_via_generated_config_and_status_reports_effective_target tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_available_participation_evidence`

Acceptance criteria:
- desired and effective stable runtime consumer truth are reported separately
- healthcheck insufficiency vs launch-smoke sufficiency is explicit
- claim-gate result after reproof is explicit
- next contour is named exactly

Verification:
- tests:
  - targeted runtime/rotation tests pass
- build:
  - `git diff --check`
- manual:
  - healthcheck leaves activation gap unresolved
  - launch smoke refreshes activation evidence and aligns effective consumer truth
  - post-smoke status clears claim_gate and policy_drift
  - post-smoke rotation remains fresh/present
- live packet:
  - launch packet, post-smoke status packet, post-smoke rotation packet

Artifacts:
- spec:
  - `audit_results/runtime_reproof_pass_2026-05-16_v3/contour.md`
- packet:
  - `runtime_basis.json`
  - `owner_path_reproof_packets.json`
  - `runtime_truth_classification.json`
  - `claim_gate_evaluation.json`
  - `anti_loop_evaluation.json`
  - `decision_packet.json`
- closeout note:
  - `closeout.md`

Stop conditions:
- owner-path packets contradict each other
- runtime reproof would require non-canonical manual activation
- exact next contour cannot be named honestly from the packets

Closeout:
- verification complete: pending
- commit: pending
- push: pending
- next contour: `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
