# Spec: DESKTOP_EXECUTABLE_BRIDGE_ADMISSION_PASS

## Objective

Prove one real executable desktop shell/bridge path that stays admission-only,
uses a bounded packet + refresh flow, and does not widen beyond the proven web
sandbox truth contract.

## In Scope

- use the existing Tk desktop shell as the executable desktop surface
- add one bounded desktop bridge lane for
  `external-models profile codex-desktop --route <route> --json`
- refresh external-models truth after the profile packet
- prove the path with tests and executable smoke evidence

## Out of Scope

- full desktop Quick Start parity
- desktop redesign or polish
- packaging
- new desktop-only command surfaces
- raw desktop path/auth/secret/token inputs on the new lane

## Constraints

- packet truth and refresh truth remain the only machine truth
- desktop layer must not become a new source of runtime truth
- selected route must come from refreshed route truth, not freeform input
- the new lane must remain non-mutating and support-only

## Assumptions

- the bundled runtime Python is the executable desktop proof target because it
  includes Tk support
- the existing Tk shell is a legitimate desktop shell surface for this contour

## Acceptance Criteria

- [x] real executable desktop shell path proven via `ui_shell.py` on the bundled runtime
- [x] one minimal admitted packet + refresh flow works in the desktop layer
- [x] no forbidden desktop-only input widening on the new path
- [x] desktop bridge remains admission-only, not parity
- [x] independent audit finds no medium+ issues

## Verification

- tests:
  - `python3 -B -m unittest tests.test_ui_shell -q`
  - `python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - executable Tk smoke with real CLI-backed packet/refresh flow
- live evidence:
  - desktop shell route selection produced `profile_packet_only`
    `codex_desktop_openai_compatible` without config mutation

## Open Questions

- whether the later desktop parity contour should port the web Quick Start
  operator flow into this Tk shell or a different admitted desktop surface
