command: `python3 -m wild_boar_proxy sync --json`

expected write surfaces:
- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

expected truth change:
- `rollout rotation inspect --json.machine_error_code`: `ROTATION_EVIDENCE_STALE` -> `OK`
- `rotation_evidence_result.evidence_freshness`: `stale` -> `fresh`
- `rotation_evidence_result.participation_status`: `stale` -> `available`

rollback expectation:
- if the admitted step returns strict JSON but reopens upstream runtime truth,
  close `NO_GO_RUNTIME_REGRESSION` and do not widen the contour

canon distinction:
- `rollout rotation inspect --json` validates bounded evidence only
- `runtime_state.selected_backend_snapshot` may be materialized only by the
  serialized runtime-state owner path in `sync --json`
- explicit live owner authorization is present in the active operator thread
