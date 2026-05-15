# SANDBOX_LIVE_SERVER_BINDING_PASS Closeout

## Goal

Prove that the command runner, live read-only server, and UI read-only screens bind to sandbox-local paths under `/Users/kirillponomarev/.codex-custom-test` rather than silently reading or mutating the live work contour.

## Result

- status: completed
- final verdict: GO_TO_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS
- next action: run sandbox onboarding reserve-first proof using the same sandbox-local env binding

## Contour Capsule

- goal: prove sandbox-local source binding from command packets through live GET packets into the core UI read-only screens
- branch: `codex/external-agent-lab-isolated`
- head: `0532db8 Finalize sandbox scaffold closeout metadata`
- touched files: `audit_results/sandbox_live_server_binding_pass_2026-05-15/*`
- tests run: sandbox command packet capture; live readonly GET capture; browser-based final screen capture; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/sandbox_live_server_binding_pass_2026-05-15/closeout.md`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: sandbox-root `auth.json` and `config.toml` remain pre-existing files and are not readiness proof; next contour must still treat onboarding as a fresh mutation proof
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests: command `changed_files` stayed inside `/Users/kirillponomarev/.codex-custom-test`; `status` packet path evidence references sandbox-local `supervisor-state.json` and launcher path; external-models packet paths reference sandbox-local routes/state/secrets; forbidden live-path drift remained false
- build: not applicable
- manual: verified final UI read-only renders for `quick-start`, `overview`, `accounts`, and `api-connections` against sandbox packets and saved screenshots
- live verification: `/api/live-readonly` returned honest `integration_failure` from sandbox attestation failure; `/api/accounts-readonly` and `/api/api-connections-readonly` returned sandbox-local empty/neutral state without work-contour leakage

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/risk_matrix.md`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_live_server_binding_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at artifact drafting time
- pushed: pending at artifact drafting time

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; no live auth contents or raw logs were copied into artifacts, and UI captures remained bounded to visible read-only state

## Notes

- blockers encountered: none blocking the binding verdict; the only carried-forward caution is that sandbox-local auth/config presence is not operational readiness proof
- follow-up contour: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
- resume from here: `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
