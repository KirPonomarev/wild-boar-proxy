<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Sandbox Runtime And DeepSeek Parity Fix Gate Closeout

## Goal

Close the sandbox/runtime/API truth split so web readonly packets and sandbox CLI
packets report the same target truth before any broader runtime, UI, or app
launch contour starts.

## Result

- status: completed
- final verdict: `closed_success`
- next action: start `FULL_SYSTEM_RUNTIME_AND_PROXY_PROOF_PASS`

## Contour Capsule

- goal: restore sandbox parity across CLI runtime, CLI external-models, and web readonly surfaces
- branch: `codex/external-agent-lab-isolated`
- head: `cef4ca9` at contour start
- touched files:
  - `wild_boar_proxy/external_models/paths.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `tests/test_external_models.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/*`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_external_models tests.test_web_design_live_server tests.test_cli_external_models -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- blocked risks:
  - reserve-first `policy_drift` remains open but is explicitly outside this contour scope
  - readonly summary sibling-state coverage can still be broadened later
- next exact command: `python3 -m wild_boar_proxy status --json`

## Verification

- tests:
  - 112 focused tests passed
  - external-models fallback regression covered
  - web readonly validation-failure regression covered
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed
  - `git diff --check` passed
- manual:
  - sandbox `external-models routes list --json` worked without explicit `WBP_EXTERNAL_MODELS_DIR`
  - sandbox `external-models check --route wbp-deepseek-v3 --json` returned `OK`
- live verification:
  - sandbox `status --json` returned `OK`
  - sandbox `healthcheck --json` returned `OK`
  - `curl http://127.0.0.1:8788/api/live-readonly` returned healthy runtime truth
  - `curl http://127.0.0.1:8788/api/api-connections-readonly` returned the same route truth

## Artifacts

- spec: [spec.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/spec.md)
- packet:
  - [baseline.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/baseline.json)
  - [root_cause.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/root_cause.json)
  - [repair_actions.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/repair_actions.json)
  - [proof.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/proof.json)
  - [redaction_audit.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/redaction_audit.json)
  - [independent_audit.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/independent_audit.json)
- report: [closeout.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_runtime_and_deepseek_parity_fix_gate_2026-05-23/closeout.md)

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no; existing unrelated untracked files were left untouched
- private-data risk reviewed: yes; runtime auth was repaired inside sandbox only, with no secret values written to repo artifacts

## Notes

- blockers encountered:
  - sandbox runtime attestation failed with `HTTP 401 Invalid API key`
  - sandbox CLI external-models path diverged from web sandbox target unless `WBP_EXTERNAL_MODELS_DIR` was set explicitly
  - web readonly summary initially undercounted provider validation failure after row-state downgrade
- follow-up contour: `FULL_SYSTEM_RUNTIME_AND_PROXY_PROOF_PASS`
- resume from here: `python3 -m wild_boar_proxy status --json`
