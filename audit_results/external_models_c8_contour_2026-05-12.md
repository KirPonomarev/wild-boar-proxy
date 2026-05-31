<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C8 Contour

## Contour

- contour_id: `external_models_c8_custom_transforms_contract_and_mocked_execution`
- date_utc: `2026-05-12`
- branch: `codex/external-agent-lab-isolated`
- base_head_before_c8: `e04077e`
- mode: `implementation`

## Goal

Add bounded declarative transform profiles for external-models request/response
compatibility without widening execution power, duplicating a generic engine, or
changing runtime truth semantics.

## Scope

In scope:

- allowlisted optional route fields:
  - `transform_profile`
  - `response_profile`
- bounded request transform application during `external-models check`
- bounded response extraction during `external-models check`
- transform metadata in `validate` and `check` packets/evidence
- schema validation and rejection of unknown profiles
- focused tests for schema and mocked transform execution

Out of scope:

- arbitrary code execution
- dynamic transform loading
- tool execution
- runtime truth changes
- Codex config mutation
- live-path reopening

## Files Changed

- `wild_boar_proxy/external_models/contracts.py`
- `wild_boar_proxy/external_models/routes.py`
- `wild_boar_proxy/external_models/transforms.py`
- `wild_boar_proxy/external_models/validate.py`
- `tests/test_external_models.py`
- `tests/test_cli_external_models.py`

## Verification

Executed:

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

Manual isolated probe:

- added route with:
  - `transform_profile=openai_chat_input_text`
  - `response_profile=top_level_output_text`
- `external-models check --json --route wbp-deepseek-v3` returned:
  - `status=ok`
  - `request_shape=input_text`
  - `response_shape=output_text`
- mocked provider captured request keys:
  - `["input_text", "max_output_tokens", "model"]`

## Scope Integrity

- no changes to main runtime truth surfaces
- no CLI command-surface expansion
- no tool/sandbox execution surface introduced
- unrelated dirty files in:
  - `external_agent_lab/*`
  - `tests/test_external_agent_lab.py`
  - `wild_boar_proxy/runtime.py`
  remained out of contour scope
