<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

CONTOUR:
WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS

Goal:
Add one safe web dry-run flow for account connection that shows a truthful
preview/result surface without performing real onboarding, auth import,
registry mutation, or runtime-state mutation.

Size: S/M
Risk level: medium-high
Decision owner: Maintainer, with canon as truth boundary
Mode: web + control-layer dry-run action

In scope:
- add one visible web affordance for account-connect dry-run preview
- keep browser payload bounded to `ui_action` only
- return a server-owned preview packet with no write surface
- render preview-only onboarding result states without false success
- add targeted tests and one browser click verification

Out of scope:
- no real account connection
- no auth import
- no registry write
- no runtime mutation
- no browser file selection
- no CLI or desktop shell onboarding changes

Assumptions:
- live onboarding remains a later contour
- preview-only result is useful even without real candidate discovery
- current working Codex session must remain untouched

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `AGENTS.md`
- code:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
- runtime evidence:
  - local preview server browser click only

Commands / files:
- touched runtime/control files:
  - `wild_boar_proxy/web_design_live_server.py`
- touched UI files:
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
- touched tests:
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`

Acceptance criteria:
- visible UI button launches only dry-run preview
- browser payload contains no path, token, secret, auth file, argv, or upload
- result surface says preview only and never claims connected/success
- no selected backend is shown for dry-run preview
- no real command onboarding or registry mutation runs
- current working Codex session remains untouched

Verification:
- tests:
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`
- build:
  - `git diff --check`
  - `python3 -m json.tool audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/decision_packet.json`
- manual:
  - browser click on `?screen=accounts&source=live`
  - open dry-run modal
  - click preview button
  - verify preview-only banner and non-green panel
- live packet:
  - no live account connection performed

Artifacts:
- spec:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/closeout.md`

Stop conditions:
- stop if implementation requires auth import or browser file input
- stop if preview cannot stay distinct from success
- stop if current working Codex session could be touched

Closeout:
- verification complete before commit
- commit and push required
- next contour:
  - `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS`
