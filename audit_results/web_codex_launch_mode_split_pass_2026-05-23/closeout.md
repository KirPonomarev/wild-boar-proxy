<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_CODEX_LAUNCH_MODE_SPLIT_PASS Closeout

## Goal

Separate `Original Codex` and `Codex Custom` in the WBP web/control layer with
dry-run/readiness packets only.

## Result

- status: passed
- final verdict: `WEB_CODEX_LAUNCH_MODE_SPLIT_READY`
- next action: `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS`

## Contour Capsule

- goal: prove web/control launch-mode split without launching Codex or running live inference
- branch: codex/external-agent-lab-isolated
- head: 3cad6db before contour commit
- touched files: wild_boar_proxy/codex_launch_modes.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_codex_launch_modes.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; audit_results/web_codex_launch_mode_split_pass_2026-05-23/*
- tests run: node --check overview.js; project Python targeted unittest suite; project Python extended 661-test suite; git diff --check; browser fake-server click proof
- blocked risks: live launch, live prompt, account/API mutation, and current Codex mutation were kept out of scope by dry-run packets
- next exact command: plan `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS`

## Verification

- tests: `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_codex_launch_modes tests.test_web_design_live_server tests.test_web_design_ui -q` passed with 159 tests; extended CLI/web/Codex suite passed with 661 tests
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed; `git diff --check` passed
- manual: Codex in-app browser clicked both dry-run buttons on a fake no-runtime local server
- live verification: not run because this contour intentionally excludes live runtime/account/API prompts

## Artifacts

- spec: audit_results/web_codex_launch_mode_split_pass_2026-05-23/spec.md
- packet: audit_results/web_codex_launch_mode_split_pass_2026-05-23/proof.json
- report: audit_results/web_codex_launch_mode_split_pass_2026-05-23/browser_proof.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout is staged
- pushed: pushed after contour commit

## Scope Check

- unrelated work mixed in: no; unrelated existing untracked files were ignored
- private-data risk reviewed: yes; no auth contents, tokens, runtime state, or account/API packets captured

## Notes

- blockers encountered: system `python3` lacked `_tkinter` and `PIL`; project Python runtime was used for tests
- follow-up contour: `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS`
- resume from here: CLOSED
