command: `python3 -m wild_boar_proxy launch smoke --json`

expected write surfaces:
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`

expected truth change:
- `effective_mode`: `managed` -> `stable`
- `claim_gate.status`: `blocked` -> `clear`
- `policy_drift.status`: `detected` -> `clear`
- `stable_runtime_consumer.consumer_activation_readiness`: `STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING` -> `OK`
- stable-runtime effective source matches desired approved repair target

rollback expectation:
- if the admitted step returns strict JSON but postflight regresses broader
  runtime truth, close `NO_GO_RUNTIME_REGRESSION` and do not widen the contour

canon distinction:
- deterministic stable recovery result remains owned by `healthcheck --json`
- this contour uses `launch smoke --json` only for the bounded activation lane
  explicitly exposed by the stable-runtime consumer contract
