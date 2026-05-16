<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

CONTOUR:
WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS

Goal:
Connect one existing admitted server-owned live onboarding path into the web UI,
with reserve-first proof requirements, existing readonly refresh only, and no
broadening of onboarding/auth/runtime architecture.

Size:
M

Risk level:
high

Decision owner:
Canon decides disputed questions of live admission, write boundary, and
truthful success criteria. Maintainer owns code, tests, and browser
verification.

Mode:
web + control-layer live action

In scope:
- switch the visible account-connect affordance from preview-only to one
  existing server-owned live onboarding path
- gate live onboarding with a server-owned accounts-readonly preflight
- keep browser payload bounded with no auth file, token, secret, path, upload,
  source_dir, backend_id, or argv surface
- keep post-action refresh limited to existing accounts-readonly refresh
- preserve truthful reserve-first-only result rendering
- add/update targeted tests and run a browser click verification

Out of scope:
- no new onboarding engine
- no broad onboarding/runtime refactor
- no browser auth input
- no design polish
- no desktop port
- no stage/pilot claims

Acceptance criteria:
- web UI triggers exactly one existing admitted server-owned live onboarding
  path
- live request is blocked when server-owned preflight is not admitted
- success is claimed only when reserve-first proof is present
- UI does not overclaim active-ready or “ready for use”
- current working Codex session remains untouched
- next contour remains WEB_DESIGN_FINISH_PASS

Verification:
- tests:
  - python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui
- build:
  - git diff --check
  - python3 -m json.tool audit_results/web_safe_account_connect_live_pass_2026-05-16/decision_packet.json
- manual:
  - verify accounts buttons point to onboard_account
  - verify onboarding modal copy describes live reserve-first flow
- live packet:
  - browser click against a local fake live server at
    http://127.0.0.1:8765/?screen=accounts&source=live

Artifacts:
- spec:
  - audit_results/web_safe_account_connect_live_pass_2026-05-16/contour.md
- packet:
  - audit_results/web_safe_account_connect_live_pass_2026-05-16/decision_packet.json
- closeout note:
  - audit_results/web_safe_account_connect_live_pass_2026-05-16/closeout.md

Stop conditions:
- STOP_AND_DIAGNOSE if live connect requires browser auth input
- STOP_AND_DIAGNOSE if post-action refresh requires a new proof pipeline
- STOP_AND_DIAGNOSE if the contour drifts into a broad onboarding refactor
- STOP_AND_DIAGNOSE if current working Codex could be touched

Closeout:
- verification complete:
  - targeted tests pass
  - browser click verification passes on a fake live server
  - decision packet JSON parses
  - git diff --check passes
  - closeout resilience passes
- commit:
  - required
- push:
  - required
- next contour:
  - WEB_DESIGN_FINISH_PASS
