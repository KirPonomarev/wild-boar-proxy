# Spec: OWNER_LEGACY_RUNTIME_SURFACES_ADMISSION_PASS

## Objective

Promote proven legacy owner/runtime mechanics from `~/.codex-custom-cli` into
repo-owned code without introducing a second runtime-truth surface.

## In Scope

- legacy local proxy candidate discovery and bounded reprobe helpers
- stale managed pid cleanup and richer managed proof inside canonical
  `healthcheck --json`
- repo-managed operator wrappers for `Add Account.command` and
  `team-codex-login.command`
- targeted regression tests and contour artifacts

## Out of Scope

- web wiring or browser login flow
- provider OAuth or external auth callbacks
- desktop redesign or packaging
- API route create/adopt

## Constraints

- Canon order: `CANON.md` -> `MASTER_PLAN.md` -> `RUNTIME_CONTRACT.md` ->
  `STATE_SCHEMA.md` -> `COMMAND_API.md` -> `DELIVERY_RULES.md` -> `README.md`
- live runtime truth remains `healthcheck --json`
- candidate proxy existence alone must never produce green status
- repo-managed wrappers must not overwrite unmarked user-owned files
- no secrets/tokens/auth paths may be committed

## Assumptions

- Existing runtime proof and sync commands remain authoritative; this contour
  only strengthens their helper logic and wrapper materialization.
- Legacy shell behaviors can be represented safely in repo-owned Python and
  generated wrapper scripts.

## Acceptance Criteria

- [x] legacy proxy candidate defaults `10808/10809` are appended as bounded
  helpers instead of becoming a new truth surface
- [x] dynamic local listener candidates are parsed, de-duplicated, and exclude
  service ports such as `8318/8319/8320/8321`
- [x] `healthcheck --json` clears stale managed pid state before proof decisions
- [x] `/v1/responses` probe sends `X-Session-ID`
- [x] proxy-path failure cases remain non-green without live reproof
- [x] installer materializes repo-managed `Add Account.command` and
  `team-codex-login.command` wrappers
- [x] unmarked operator wrappers are preserved instead of being overwritten
- [x] wrapper payloads contain no secrets and target owner-owned lanes only
- [x] `tests.test_cli` passes after the changes
- [x] required secondary verification commands pass

## Verification

- tests:
  - `python3 -m unittest tests.test_cli -q`
  - bundled runtime python:
    `-m unittest tests.test_web_design_live_server tests.test_web_design_command_adapter tests.test_ui_shell -q`
  - targeted `tests.test_cli` cases for wrappers, proxy candidates, reprobe, and
    `X-Session-ID`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- manual:
  - diff/stat review for wrapper payloads and runtime helper placement
- live evidence:
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/test-gate-summary.txt`
  - `audit_results/owner_legacy_runtime_surfaces_admission_pass_2026-05-22/evidence/runtime-surface-summary.txt`

## Open Questions

- None for this contour. The next contour decides how web bridges into the
  owner-owned login/onboard surface.
