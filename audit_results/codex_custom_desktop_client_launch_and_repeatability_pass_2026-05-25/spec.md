# Spec: Codex Custom Desktop Client Launch And Repeatability

## Objective

Close the local desktop-launch gap inside active `CODEX_CUSTOM_LAUNCH_AND_ROUTE_E2E_COMPLETION_PASS` by proving that WBP can trigger a real isolated Codex Custom desktop client launch, that the GPT-account lane remains usable across repeated runs, and that cleanup stays bounded. Do not overclaim full `8B` completion while external API proof is still blocked by missing owner credential.

## In Scope

- prove `real_codex_app_launched=true` for the existing `launch client --json` surface
- wire the live web action path to the isolated launch-copy runner so the live server can dispatch the real client launch
- repeat desktop launch, GPT-account prompt, and cleanup checks three times
- capture machine-readable repeatability evidence
- capture browser-driven DOM proof and an honest screenshot-blocked packet
- record current accounts/API repeated truth without upgrading it beyond what packets prove

## Out of Scope

- external API provider credential admission
- external API route success claims
- full `8B` completion claim
- new route framework or credential mechanism
- UI design expansion or polish

## Constraints

- keep active product contour as `CODEX_CUSTOM_LAUNCH_AND_ROUTE_E2E_COMPLETION_PASS`
- no new `8C` branch
- `workbench_ready` alone does not count as desktop client launch
- browser screenshot capture must be marked blocked if the environment cannot actually produce PNG proof
- current Codex must remain untouched

## Assumptions

- `/Applications/Codex.app/Contents/MacOS/Codex` exists and is launchable on the host
- the isolated copied profile/managed pair is sufficient for bounded desktop launch proof
- external API proof remains blocked until owner-side provider credential exists in the active process environment

## Acceptance Criteria

- [x] live launch-client path can prove `real_codex_app_launched=true`
- [x] live launch-client path is distinguished from `workbench_ready`-only custom launch truth
- [x] desktop launch, GPT-account prompt, and cleanup complete successfully across three runs
- [x] repeated external credential checks remain honestly blocked with `EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING`
- [x] browser-driven DOM proof exists, and PNG screenshot capture is either real or explicitly blocked with evidence
- [x] active `8B` remains `partial_blocked`

## Verification

- tests:
  - `python3 -m unittest tests.test_cli -q`
  - `python3 -m unittest tests.test_web_design_live_server tests.test_web_design_ui -q`
- build:
  - `python3 -m py_compile /Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py /Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_live_server.py /Volumes/Work/wild-boar-proxy/tests/test_cli.py /Volumes/Work/wild-boar-proxy/tests/test_web_design_live_server.py`
  - `node --check /Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_ui/scripts/overview.js`
- manual:
  - live HTTP packet collection against `http://127.0.0.1:57377`
- live evidence:
  - repeated launch/prompt/cleanup packets in `evidence/runs/`
  - `desktop_launch_repeatability_summary.json`
  - `browser_dom_proof_summary.json`
  - `screenshot_blocked_packet.json`

## Open Questions

- none for the local desktop-launch slice; the only remaining product blocker is the owner-side external provider credential for full `8B` closure
