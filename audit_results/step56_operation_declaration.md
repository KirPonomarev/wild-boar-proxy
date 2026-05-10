Live operation declaration for `TOP_LEVEL_RUNTIME_TRUTH_REPAIR_CONTOUR`

Admitted owner surface:
- `python3 -m wild_boar_proxy launch smoke --json`

Expected write surfaces:
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

Expected truth change:
- `claim_gate.status` moves from `blocked` to `clear`
- `policy_drift.status` moves from `detected` to `clear`
- `stable_runtime_consumer.consumer_activation_readiness.machine_error_code`
  moves from `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING` to `OK`
- effective stable-runtime consumer source matches desired source
- activation evidence is no longer stale

Rollback expectation:
- owner packet must expose truthful `changed_files`
- if activation fails or verification fails, contour closes `NO_GO` and does
  not widen into `sync --json` or mixed-lane repair

Stop conditions before mutation:
- independent inspection rejects `launch smoke --json` as the admitted owner lane
- fresh contradictory runtime truth appears that invalidates the lane
- command fails to return strict JSON owner packet
