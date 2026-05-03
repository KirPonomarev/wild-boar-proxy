# Runtime Contract

## Modes

- `stable`
- `managed`

## Ports

- stable endpoint: `8318`
- managed endpoint: `8320`

## Truth rules

- desired mode is stored separately from effective mode
- effective mode is written only after successful live preflight
- live listener truth wins over cached state
- missing managed listener means managed is down
- fallback to stable must be explicit and observable

## Safety rules

- stale pid files must be cleaned before decisions are made
- lock handling must prevent overlapping sync flows
- closing the UI must not silently kill a healthy backend
- reboot recovery must either restore cleanly or report down honestly
