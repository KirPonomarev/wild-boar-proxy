<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Command API Contract

All operator commands must support `--json`.

## JSON output rules

- `stdout` must contain exactly one JSON object
- `stdout` must not contain leading or trailing non-JSON text
- `stderr` may contain human-readable logs
- invalid JSON is a hard integration failure even when exit code is `0`
- UI and automation must not fall back to plain-text parsing or log parsing

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

Every command response must include all required fields on both success and failure.

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`

## Response rules

- `status` must not collapse liveness, severity, and operator action into one ambiguous token
- `exit_code` must reflect command success or failure
- `human_message` is for operator-readable summary, not machine parsing
- `machine_error_code` must be stable enough for UI and automation branching
- `changed_files` must be an array and may be empty
- `next_action` must be present even when the correct action is `none`
- `next_action` must use documented machine-readable tokens such as `none`,
  `retry`, `user_action`, or `stop`
- commands that report runtime health must expose `liveness`, `severity`, and
  `operator_action` as separate top-level fields instead of overloading
  `status`
- commands that carry runtime attestation must expose an `attestation` object
  containing the required attestation fields from `RUNTIME_CONTRACT.md`

## Error classes

- `recoverable`
- `needs_user_action`
- `fatal`
