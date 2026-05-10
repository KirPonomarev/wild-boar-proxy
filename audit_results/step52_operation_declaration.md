# Step52 Operation Declaration

## Admitted owner lane

- `launch smoke --json`

## Reason

The selected primary blocker is `top_level_runtime_truth_regression`.

Fresh preflight confirms:

- `desired_mode=stable`
- `effective_mode=managed`
- `claim_gate.status=blocked`
- `policy_drift.status=detected`
- `stable_runtime_consumer.desired_stable_runtime_consumer_source=approved_repair_target`
- `stable_runtime_consumer.effective_stable_runtime_consumer_source=observed_stable_inventory_source`
- `stable_runtime_consumer.activation_evidence_surface.status=snapshot_stale`
- `stable_runtime_consumer.consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`

By contract, `launch smoke --json` is the narrow stable-runtime activation seam.
This contour does not admit `sync --json` as a second external owner surface.

## Expected write surfaces

- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

## Expected effect

- launcher-scoped stable runtime activation is re-attempted
- effective stable-runtime consumer source aligns with desired source
- activation evidence becomes fresh and machine-readable
- top-level runtime truth returns to:
  - `effective_mode=stable`
  - `claim_gate.status=clear`
  - `policy_drift.status=clear`

## Rollback expectation

- no manual rollback inside this contour
- if the one admitted owner lane fails or leaves top-level truth non-green,
  contour closes `NO_GO` and widens nothing

## Stop conditions

- any invalid JSON packet
- new foreign lock-holder before execution
- command output contract mismatch
- need for a second external owner surface
