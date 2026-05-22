<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Sandbox Runtime And DeepSeek Parity Fix Gate

## Objective

Close the sandbox/runtime/API truth split so the same sandbox target produces the
same truth via web readonly surfaces and CLI JSON command packets.

## In Scope

- fix `external-models` root resolution when `WBP_MANAGED_DIR` is set and
  `WBP_EXTERNAL_MODELS_DIR` is unset
- repair sandbox runtime auth surface so sandbox `status --json` and
  `healthcheck --json` stop failing with `HTTP 401`
- downgrade web API connection row state when provider validation failed
- align API connections readonly summary attention counting with the downgraded
  row states
- add focused regression tests
- produce factual closeout artifacts and independent audit

## Out of Scope

- moderate load or rotation proof
- full DeepSeek product flow proof
- menu completeness
- isolated Codex app launch proof
- reserve-first lifecycle normalization

## Constraints

- do not mutate the current working Codex profile
- do not expose secret values in chat, browser, artifacts, or git diff
- use command JSON packets as primary truth
- keep repo changes scoped to parity repair only

## Assumptions

- the web server sandbox target is the launch-copy profile/data pair visible in
  the live server process arguments
- the healthy default runtime auth surface in
  `/Users/kirillponomarev/.codex-custom-cli/auth.json` is the intended
  OpenAI-key style auth shape for sandbox runtime attestation

## Acceptance Criteria

- [x] sandbox CLI resolves `external-models` root from `WBP_MANAGED_DIR` when
  `WBP_EXTERNAL_MODELS_DIR` is absent
- [x] sandbox `external-models check --route wbp-deepseek-v3 --json` passes
- [x] sandbox `status --json` no longer fails on invalid API key
- [x] sandbox `healthcheck --json` no longer fails on invalid API key
- [x] web `/api/live-readonly` and sandbox CLI agree that runtime is healthy
- [x] web API connections row and summary both reflect provider validation
  failures without overclaim
- [x] focused tests pass
- [x] independent audit finds no remaining scope-breaking overclaim in this
  contour

## Verification

- tests:
  - `python3 -B -m unittest tests.test_external_models tests.test_web_design_live_server tests.test_cli_external_models -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - sandbox CLI `status`, `healthcheck`, `external-models routes list`, and
    `external-models check`
- live evidence:
  - `curl http://127.0.0.1:8788/api/live-readonly`
  - `curl http://127.0.0.1:8788/api/api-connections-readonly`

## Open Questions

- whether additional coverage should be added later for readonly summary
  aggregation of `provider_network_failed`, `limited`, and `blocked`
  availability states
