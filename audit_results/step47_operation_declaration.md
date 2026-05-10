CONTOUR_ID: STABLE_RUNTIME_CONSUMER_ACTIVATION_LANE_RECLEAR
LIVE_OPERATION_STATUS: ADMITTED
WRITE_STEP_COUNT: 1
OWNER_COMMAND:
- `launch smoke --json`

COMMAND_JUSTIFICATION:
- `COMMAND_API.md` states that when desired source is the approved repair target, `launch smoke --json` may:
  - materialize `stable-runtime-config.generated.yaml`
  - pass `WBP_STABLE_CONFIG`
  - write `stable_runtime_consumer_snapshot`
- `sync --json` belongs to Lane B only and is forbidden in this contour

DECLARED_WRITE_SURFACES:
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh`
- managed runtime pid path if owner step rotates process state

ROLLBACK_EXPECTATION:
- no second write step is allowed in this contour
- if postflight shows Lane B regression or broader runtime regression, contour closes `NO_GO_RUNTIME_REGRESSION`
- manual rollback/edit is forbidden inside this contour

STOP_CONDITIONS:
- invalid JSON from any owner surface
- undeclared write surface touched
- Lane B regresses from `OK/fresh`
- more than one write step would be needed
- contour drifts into any non-Lane-A mutation
