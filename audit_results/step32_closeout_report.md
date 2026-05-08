# Step 32 Closeout

- Contour: `Repo-Owned Stable Launcher Provisioning For Claim-Gate Reclear`
- Captured at: `2026-05-08T18:50:18Z`
- Final result: `launcher_provisioning_closed_claim_gate_still_blocked`

## Facts

- Default launcher at `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh` is now repo-managed and recognized.
- Backup exists at `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh.pre-step32-20260508T184658Z.bak`.
- `healthcheck --json` returned `OK` with:
  - `desired_mode=stable`
  - `effective_mode=managed`
  - `current_proxy_url=http://127.0.0.1:10808`
  - `repo_owned_default_consumer_provisioned=true`
- `launch smoke --json` returned `PROXY_PATH_BROKEN` with:
  - `desired_mode=stable`
  - `effective_mode=stable`
  - `current_proxy_url=http://127.0.0.1:12334`
  - `launcher_exit_code=0`
  - `consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
  - `effective_stable_runtime_consumer_source=observed_stable_inventory_source`
- Immediate `status --json` returned `OK`, but:
  - `claim_gate.status=blocked`
  - `claim_gate.machine_error_code=CLAIM_GATE_BLOCKED`
  - `policy_drift.status=detected`
  - `launch_readiness.blocking_reason=proxy_truth_drift`
  - `effective_stable_runtime_consumer_source.matches_desired=false`

## Independent audit

- Agent: `Carver`
- `contour_status=blocked`
- `root_blocker=proxy_truth_drift`
- `launcher_provisioning_closed=true`
- `next_step=repair_proxy_truth_mismatch_then_rerun_launch_smoke`
