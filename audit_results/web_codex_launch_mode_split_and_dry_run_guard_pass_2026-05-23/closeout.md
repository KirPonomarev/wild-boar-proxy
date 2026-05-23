# WEB_CODEX_LAUNCH_MODE_SPLIT_AND_DRY_RUN_GUARD_PASS Closeout

## Goal

Separate Original Codex and Codex Custom in the WBP web UI and backend packets, prove Original Codex dry-run guard safety, and keep Codex Custom as readonly readiness only.

## Result

- status: passed
- final verdict: launch modes are separated; Original is protected dry-run only; Custom is readonly readiness only; claim gate remains blocked and visible
- next action: commit and push this contour, then continue to `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS`

## Contour Capsule

- goal: separate Original Codex protected baseline from Codex Custom proxy workbench without launching either path live
- branch: codex/external-agent-lab-isolated
- head: 3cd22be contour commit
- touched files: wild_boar_proxy/codex_launch_modes.py, wild_boar_proxy/web_design_live_server.py, wild_boar_proxy/web_design_ui/index.html, wild_boar_proxy/web_design_ui/scripts/overview.js, tests/test_codex_launch_modes.py, tests/test_web_design_live_server.py, audit_results/web_codex_launch_mode_split_and_dry_run_guard_pass_2026-05-23/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; python runtime unittest full web/custom gate; git diff --check; browser dry-run proof
- blocked risks: claim_gate remains blocked; no live Original launch; no live Custom launch; Custom status degraded with CLAIM_GATE_BLOCKED
- next exact command: git push origin codex/external-agent-lab-isolated

## Verification

- tests: full command listed in final verification output
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> OK; `git diff --check` -> OK
- manual: browser proof on `http://127.0.0.1:8793/?source=live&screen=overview` returned `dry-run safe / gate blocked`
- live verification: Original dry-run packet reports `dispatch_plan_safe=true`, `proxy_env_injected=false`, `custom_home_injected=false`, `model_override_injected=false`, `route_or_backend_injected=false`

## Artifacts

- spec: `audit_results/web_codex_launch_mode_split_and_dry_run_guard_pass_2026-05-23/spec.md`
- packet: `audit_results/web_codex_launch_mode_split_and_dry_run_guard_pass_2026-05-23/original_dry_run_guard_proof.json`
- report: `audit_results/web_codex_launch_mode_split_and_dry_run_guard_pass_2026-05-23/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: 3cd22be Split Codex launch modes in web UI
- pushed: pending push after closeout git-truth update

## Scope Check

- unrelated work mixed in: no; pre-existing unrelated untracked files were ignored
- private-data risk reviewed: yes; redaction audit reports no raw secret findings and browser forbidden DOM findings are empty

## Notes

- blockers encountered: packet-level false-green risk in Custom status was repaired by returning `degraded` and `CLAIM_GATE_BLOCKED` when claim gate is blocked
- follow-up contour: `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS`
- resume from here: CLOSED
