# Command API Contract

All operator commands must support `--json`.

## Required commands

- `status --json`
- `sync --json`
- `healthcheck --json`
- `mode get --json`
- `mode set stable --json`
- `mode set managed --json`
- `accounts list --json`
- `accounts validate <id> --json`
- `accounts promote <id> --json`
- `accounts demote <id> --json`
- `accounts hold <id> --json`
- `accounts release <id> --json`
- `accounts retire <id> --json`
- `accounts onboard --json`
- `diagnostics export --json`

## Required response fields

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`

## Error classes

- `recoverable`
- `needs_user_action`
- `fatal`
