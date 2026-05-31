<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C8 Closeout

## Result

`external_models_c8_custom_transforms_contract_and_mocked_execution` completed
with bounded declarative transform profiles and mocked execution coverage.

## Verified Facts

- optional route fields added:
  - `transform_profile`
  - `response_profile`
- unknown profiles are rejected canonically with `schema_invalid`
- `check` can apply bounded request/response profiles and emits transform
  metadata in packet/evidence
- `validate` remains route-provider-only and now carries declared transform
  metadata without changing runtime truth semantics
- no arbitrary code execution path was introduced
- no tool/sandbox execution path was introduced

## Verification

- `python3 -m unittest -q tests.test_external_models`
  - `Ran 11 tests ... OK`
- `python3 -m unittest -q tests.test_cli_external_models`
  - `Ran 17 tests ... OK`
- `python3 -m unittest -q tests.test_cli -k package`
  - `Ran 9 tests ... OK`
- `python3 -m compileall -q wild_boar_proxy tests`
  - passed
- `git diff --check`
  - passed

Manual isolated probe passed with:

- `check_status=ok`
- `request_shape=input_text`
- `response_shape=output_text`
- mocked provider request keys:
  - `input_text`
  - `max_output_tokens`
  - `model`

## Independent Audit

- artifact:
  - `audit_results/external_models_c8_independent_audit_2026-05-12.json`
- verdict:
  - `PASS`
- findings:
  - none

## Scope Note

Unrelated dirty worktree content remained outside contour scope and was not
reverted or mixed into C8.

## Git Closeout

- branch:
  - `codex/external-agent-lab-isolated`
- base_head_before_c8:
  - `e04077e`
- contour commit:
  - `4e84c25`
- push:
  - `origin/codex/external-agent-lab-isolated`
