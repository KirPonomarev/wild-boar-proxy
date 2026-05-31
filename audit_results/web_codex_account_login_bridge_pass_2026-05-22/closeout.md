# WEB_CODEX_ACCOUNT_LOGIN_BRIDGE_PASS Closeout

## Goal

Make the web `Подключить аккаунт` live path use the real Codex owner onboarding lane instead of sandbox synthetic login completion.

## Result

- status: completed
- final verdict: closed_success
- next action: `ACCOUNT_VALIDATE_AND_PROMOTE_FROM_RESERVE_PASS` only if the operator wants newly added reserve accounts promoted into the working active pool.

## Contour Capsule

- goal: `web click -> accounts onboard --json -> engine-owned Codex login/onboard lane -> sandbox auth -> reserve account -> refresh proof`
- branch: `codex/external-agent-lab-isolated`
- head: pending commit for this closeout
- touched files: `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/runtime.py`, `wild_boar_proxy/sandbox_owner_helpers.py`, `tests/test_cli.py`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`, `audit_results/web_codex_account_login_bridge_pass_2026-05-22/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; targeted unittest checks; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`; `git diff --check`
- blocked risks: real physical provider browser UX depends on `cli-proxy-api -codex-login`; WBP bridge now delegates to that owner lane and enforces sandbox paths
- next exact command: `git status --short && python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests: full required unittest gate passed, 668 tests.
- build: JS syntax check and whitespace diff check passed.
- manual: diff reviewed against canon boundaries.
- live verification: browser-context sandbox proof passed with `provider=codex`, `final_outcome=reserve_only_success`, `reserve_first_proven=true`, `active_routing_changed=false`, and reserve account `browser-proof`.

## Artifacts

- spec: `audit_results/web_codex_account_login_bridge_pass_2026-05-22/spec.md`
- packet: `audit_results/web_codex_account_login_bridge_pass_2026-05-22/evidence/action-packet.json`
- report: `audit_results/web_codex_account_login_bridge_pass_2026-05-22/evidence/browser-run-summary.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; `redaction-check.json` found no secret markers in action, browser summary, or accounts refresh evidence.

## Notes

- blockers encountered: sandbox helper imported Codex auth into reserve but did not materialize sandbox `profile/auth.json`, causing post-onboard status proof failure; fixed under `WBP_REQUIRE_SANDBOX_AUTH_DIR=1`.
- follow-up contour: `ACCOUNT_VALIDATE_AND_PROMOTE_FROM_RESERVE_PASS`
- resume from here: CLOSED
