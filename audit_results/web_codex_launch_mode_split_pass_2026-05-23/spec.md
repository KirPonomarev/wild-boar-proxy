<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: WEB_CODEX_LAUNCH_MODE_SPLIT_PASS

## Objective

Make the WBP web/control layer distinguish protected `Original Codex` from
isolated `Codex Custom` without launching either one and without making live
GPT/API/runtime claims.

## In Scope

- Add server-owned Codex Custom launch dry-run packet.
- Expose `POST /api/codex/custom/launch-dry-run`.
- Show a `Custom dry-run` web button next to `Original dry-run`.
- Prove dry-run packets carry no prompt, token burn, route/backend override, or
  current `~/.codex` permission.

## Out of Scope

- Real Original Codex launch.
- Real Codex Custom launch.
- GPT account prompt.
- API provider prompt.
- Runtime/account/API mutation.
- Rotation/load.
- Desktop packaging.
- Rich design polish.

## Constraints

- `Original Codex` remains protected baseline.
- Browser cannot supply auth, path, model, route, backend, endpoint, or home
  fields for launch-mode dry-runs.
- Success is limited to dry-run/readiness packets.
- No live runtime/account/API commands are run in this contour.

## Acceptance Criteria

- [x] Original and Custom modes are distinct in server packets.
- [x] Original dry-run proves no proxy/custom home injection.
- [x] Custom dry-run proves current Codex home is forbidden.
- [x] Custom dry-run proves no real launch, no prompt, and zero token burn.
- [x] Browser-side fields for model/route/backend/base URL/home are rejected.
- [x] Web UI exposes both dry-run buttons.
- [x] Targeted tests pass on project Python.
- [x] Browser proof passes against a fake no-runtime server.

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; project Python targeted unittest suite.
- build: `git diff --check`.
- manual: in-app browser clicked Original and Custom dry-run buttons on a fake no-runtime local server.
- live evidence: not run; live runtime/account/API intentionally out of scope.

## Open Questions

- Next live launch/prompt contour still requires the exact owner authorization
  phrase from `CANON.md`.
