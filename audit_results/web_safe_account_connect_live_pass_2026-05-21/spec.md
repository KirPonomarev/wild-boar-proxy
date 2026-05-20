<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS

## Objective

Open the real reserve-first onboarding path in Quick Start for sandbox web mode,
keeping preview and live semantics separate and proving live success only from
the owner packet plus canonical accounts refresh.

## In Scope

- admit `onboard_account` in `sandbox_actions`
- keep `onboard_account_dry_run` as the preview-first lane
- switch the onboarding modal from preview to live only after an admitted
  preview in the current UI session
- derive onboarding refresh success from the accounts snapshot, not from generic
  action success or live-readonly assumptions
- extend tests for sandbox metadata, modal switching, and onboarding refresh
  truth

## Out of Scope

- API route flows
- `Проверить всё`
- lifecycle account actions
- desktop port
- rollback UI branches not present in the onboarding packet
- real sandbox mutation without canonical owner authorization in the thread

## Constraints

- browser must not submit tokens, auth files, local paths, or backend ids
- `live_readonly` must keep `onboard_account` disabled
- `sandbox_actions` must still require sandbox preflight and
  accounts-readonly preflight before dispatch
- success cannot be inferred from command exit status alone
- refresh mismatch must stay non-success

## Assumptions

- onboarding packet fields already exposed by runtime/ui shell remain canonical
- accounts readonly snapshot is the canonical refresh surface for live onboarding
- explicit owner authorization required by `CANON.md` is a contour-close gate,
  not a browser payload field

## Acceptance Criteria

- [x] `onboard_account` is available in `sandbox_actions`
- [x] `onboard_account` stays disabled in `live_readonly`
- [x] Quick Start preview can promote the modal to a live reserve-first action
  in the current session
- [x] onboarding refresh success is derived from the accounts snapshot and
  detects reserve mismatch
- [x] tests cover sandbox admission, modal switch, and canonical refresh verdict
- [ ] real sandbox live mutation executed under canonical owner authorization

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`
- build:
  - `git diff --check`
- manual:
  - stubbed local HTTP verification against `build_handler(..., action_phase=sandbox_actions)`
- live evidence:
  - blocked by missing explicit owner authorization phrase required by `CANON.md`

## Open Questions

- whether the next contour should be a short authorization-unblock live run or a
  broader command expansion depends on closeout evidence after explicit owner
  authorization is available
