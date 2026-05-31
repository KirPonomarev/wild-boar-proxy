# DESKTOP_APP_PACKAGE_PASS Closeout

## Goal

Prove a safe packaged desktop continuity baseline on the admitted launchable
artifact path: clean artifact boundary, real packaged launch, and a truthful
Quick Start flow that reaches `Check All` ready-state without widening
semantics.

## Result

- status: `closed_success`
- final verdict:
  `SAFE_PACKAGED_DESKTOP_CONTINUITY_PROVEN_ON_CANONICAL_LAUNCHABLE_PATH`
- next action:
  return to master-plan sequencing after package proof; no new blocker remains
  inside desktop packaging

## Contour Capsule

- goal: prove safe packaged launch plus baseline Quick Start continuity on the admitted launchable `.app` artifact without introducing new truth sources
- branch: `codex/external-agent-lab-isolated`
- head: `f11bcd109d90bb7b9ab2d48a24207f2619666816`
- touched files: `wild_boar_proxy/ui_shell.py`; `wild_boar_proxy/runtime.py`; `tests/test_ui_shell.py`; `tests/test_cli.py`; `audit_results/desktop_app_package_pass_2026-05-21/spec.md`; `audit_results/desktop_app_package_pass_2026-05-21/metrics.json`; `audit_results/desktop_app_package_pass_2026-05-21/independent_audit.json`; `audit_results/desktop_app_package_pass_2026-05-21/closeout.md`; `audit_results/desktop_app_package_pass_2026-05-21/evidence/*`
- tests run: `python3 -m unittest tests.test_cli.CliTests.test_package_launchable_launcher_smoke_packaged_continuity_json_works -q`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`; `python3 -m unittest -q tests.test_cli`; `node --check /Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_ui/scripts/overview.js`
- blocked risks: full `tests.test_cli` still has six failing tests, but the same six failure names reproduce on clean `f11bcd1`; recorded as residual risk in `evidence/full_test_cli_current.txt` and `evidence/head_comparison_regressions.json`
- next exact command: `git add /Volumes/Work/wild-boar-proxy/wild_boar_proxy/ui_shell.py /Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py /Volumes/Work/wild-boar-proxy/tests/test_ui_shell.py /Volumes/Work/wild-boar-proxy/tests/test_cli.py /Volumes/Work/wild-boar-proxy/audit_results/desktop_app_package_pass_2026-05-21`

## Verification

- tests:
  - targeted packaged continuity CLI test passed
  - full `tests.test_ui_shell` passed: `Ran 116 tests ... OK`
  - web/UI regression suite passed: `Ran 251 tests ... OK`
  - full `tests.test_cli` failed with six pre-existing failures; no new failure names relative to clean `f11bcd1`
- build:
  - `package launchable build` passed and produced `WildBoarProxy.app`
  - `package launchable verify` passed with checksum and boundary clean
- manual:
  - packaged launcher `WildBoarProxy.app/Contents/MacOS/WildBoarProxy --smoke-packaged-continuity-json` returned `status=ok`, `bundle_verdict=ready`
- live verification:
  - packaged smoke recorded `source=live_sandbox`, `account_status=ok`,
    `api_status=enabled`, `bundle_status=ok`, `bundle_verdict=ready`
  - packaged smoke preserved `chat_requests_before_packaged == chat_requests_after_packaged == 1`

## Artifacts

- spec:
  `/Volumes/Work/wild-boar-proxy/audit_results/desktop_app_package_pass_2026-05-21/spec.md`
- packet:
  `/Volumes/Work/wild-boar-proxy/audit_results/desktop_app_package_pass_2026-05-21/evidence/desktop_packaged_continuity_smoke.json`
- report:
  `/Volumes/Work/wild-boar-proxy/audit_results/desktop_app_package_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `d6166fb`
- pushed: `no`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes`; package contents scan and verify boundary reported no forbidden private/runtime residue hits

## Notes

- blockers encountered:
  - first packaged-smoke implementation overclaimed success on populated fields and ran a mutating route check inside the packaged shell; both issues were fixed before closeout
  - full `tests.test_cli` remains red on six pre-existing failures outside the package scope
- follow-up contour:
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` remains unearned, so any next contour must still respect the design gate
- resume from here: CLOSED
