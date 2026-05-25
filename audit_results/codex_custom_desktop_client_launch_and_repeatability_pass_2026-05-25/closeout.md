# REAL_CUSTOM_DESKTOP_CLIENT_LAUNCH_AND_REPEATABILITY Closeout

## Goal

Close the local desktop-launch gap inside active `CODEX_CUSTOM_LAUNCH_AND_ROUTE_E2E_COMPLETION_PASS` by proving a real isolated Codex Custom desktop client launch lane, repeated GPT-account workbench success, and repeated bounded cleanup, without overclaiming the still-blocked external API lane.

## Result

- status: completed
- final verdict: `LOCAL_DESKTOP_LAUNCH_GAP_CLOSED / 8B_STILL_PARTIAL_BLOCKED`
- closure state: CLOSED

## Contour Capsule

- goal: prove repeated bounded desktop-client launch alongside repeated GPT-account workbench success and bounded cleanup
- branch: `codex/external-agent-lab-isolated`
- head: `c424c85444a4a0803cd5c77e5b1ceb3db462f089` before this contour commit
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `tests/test_cli.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/spec.md`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/*`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_cli.CliTests.test_launch_client_dispatches_bounded_executable_with_sanitized_env tests.test_cli.CliTests.test_launch_client_marks_real_app_launch_when_process_stays_alive tests.test_web_design_live_server.WebDesignLiveServerTests.test_launch_client_dispatch_redacts_changed_files_in_ui_result tests.test_web_design_live_server.WebDesignLiveServerTests.test_launch_client_dispatch_reports_real_app_process_observation`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_web_design_ui`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui`
- blocked risks:
  - `EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING` keeps the external API lane blocked
  - PNG browser screenshots remain blocked by `BROWSER_SCREENSHOT_CAPTURE_UNAVAILABLE`
  - `/api/codex/custom/accounts` remains degraded via `ROTATION_EVIDENCE_STALE`
  - `recovery_stop_cleanup_live_packet.json` remains blocked with `CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_NOT_READY`
- closure state: CLOSED

## Verification

- tests:
  - targeted desktop-launch and UI tests passed on the bundled Python runtime
  - broader touched-suite run passed: `Ran 601 tests in 218.829s, OK`
- build:
  - `python3 -m py_compile /Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py /Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_live_server.py /Volumes/Work/wild-boar-proxy/tests/test_cli.py /Volumes/Work/wild-boar-proxy/tests/test_web_design_live_server.py`
  - `node --check /Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - repeated live HTTP packet collection against `http://127.0.0.1:57377`
  - browser-driven DOM proof through the live WBP UI using the in-app browser
- live verification:
  - `launch_client_dispatch` confirmed `real_codex_app_launched=true` across three runs
  - `Codex Custom` workbench launch succeeded across three runs
  - GPT-account prompt marker `WBP_CUSTOM_GPT_ACCOUNT_OK` proved across three runs
  - cleanup stayed bounded across three runs
  - external credential admit stayed blocked across three runs with the same machine code

## Artifacts

- spec:
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/spec.md`
- packet:
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/desktop_launch_repeatability_summary.json`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/verification_summary.json`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/screenshot_blocked_packet.json`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/redaction_audit.json`
- report:
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/independent_audit_report.json`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/browser_dom_proof_summary.json`
  - `audit_results/codex_custom_desktop_client_launch_and_repeatability_pass_2026-05-25/evidence/accounts_truth_root_cause.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending before contour commit
- pushed: pending before contour push

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw prompt/response, raw backend ids, and raw auth refs remained excluded or redacted in the evidence set

## Notes

- blockers encountered:
  - browser PNG screenshot capture was not available in this environment, so the contour recorded DOM proof plus a blocked screenshot packet instead of fake screenshot proof
  - the live accounts packet stayed degraded because `rollout_rotation_inspect` reported `ROTATION_EVIDENCE_STALE`
  - the external API lane remained blocked by missing owner credential and was not upgraded
- resume from here: CLOSED

