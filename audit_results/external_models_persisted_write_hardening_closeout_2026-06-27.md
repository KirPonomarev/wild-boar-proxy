<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models Persisted Write Hardening Closeout

## Goal

Close the external-models persisted JSON write-hardening stack by validating
`state.json`, `routes.json`, and `evidence/*.json` payloads before atomic
publish, while preserving route-local packet semantics.

## Result

- status: implemented and verified
- final verdict: external-models state, route registry, and evidence artifact
  writes now fail closed before publish on malformed persisted payloads; the
  route provider verification and smoke owner surfaces keep their existing
  packet shape and route-local truth boundaries
- closure state: CLOSED

## Contour Capsule

- goal: external-models persisted write hardening
- branch: `codex/stabilize-runtime-core`
- head: `3475120738dcd894d334a9da68bae2b975b8a4f7` before contour closeout commit
- touched files: `wild_boar_proxy/external_models/contracts.py`, `wild_boar_proxy/external_models/integration.py`, `wild_boar_proxy/external_models/routes.py`, `wild_boar_proxy/external_models/state.py`, `wild_boar_proxy/external_models/validate.py`, `tests/test_external_models.py`, `audit_results/external_models_persisted_write_hardening_closeout_2026-06-27.md`
- tests run: `python3 -m py_compile wild_boar_proxy/external_models/state.py wild_boar_proxy/external_models/validate.py tests/test_external_models.py`; `pytest -q tests/test_external_models.py tests/test_cli_external_models.py`; `pytest -q tests/test_ui_shell.py -k 'external_action_result or external_models_snapshot'`; `pytest -q`
- blocked risks: malformed external-models state publish, malformed routes registry publish, malformed evidence artifact publish, stale artifact digest, command-level evidence write failure without packet proof, accidental packet surface drift
- closure state: CLOSED

## Verification

- tests:
  - `pytest -q tests/test_external_models.py tests/test_cli_external_models.py` -> `72 passed, 35 subtests passed in 19.50s`
  - `pytest -q tests/test_ui_shell.py -k 'external_action_result or external_models_snapshot'` -> `6 passed, 111 deselected in 0.04s`
  - `pytest -q` -> `4181 passed, 1 skipped, 951 subtests passed in 1090.56s (0:18:10)`
- build:
  - `python3 -m py_compile wild_boar_proxy/external_models/state.py wild_boar_proxy/external_models/validate.py tests/test_external_models.py`
- manual:
  - independent inventory found two persisted external-models evidence artifact writers: local evidence capture and network evidence capture
  - independent audit confirmed no new packet fields were added or removed
  - independent audit identified the broader local stack as `state.json`, `routes.json`, and `evidence/*.json`; this closeout names that factual scope
- live verification:
  - no live provider or runtime mutation was performed

## Artifacts

- spec:
  - this closeout records the completed bounded contour; no separate spec artifact was created
- packet:
  - no live packet artifact was required
- report:
  - full pytest release gate completed green after the code and test changes;
    closeout resilience completed green after the closeout artifact was added

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the external-models code/test changes
- pushed: yes, contour branch pushed to `origin/codex/stabilize-runtime-core` in this closeout cycle

## Scope Check

- unrelated work mixed in: no staged contour file is outside external-models persisted write hardening; unrelated unstaged worktree changes were left untouched
- private-data risk reviewed: yes
- live-path mutation performed: no
- packet surface changed: no new packet fields were added or removed
- initial scope correction recorded: yes; the factual closeout scope is broader than the earlier evidence-only wording because state and routes write hardening was already present in the open local stack

## Notes

- blockers encountered: the open local stack already contained state and route
  registry write hardening, so the contour was closed under the factual
  `external-models persisted write hardening` scope rather than the narrower
  evidence-only label
- resume from here: CLOSED
