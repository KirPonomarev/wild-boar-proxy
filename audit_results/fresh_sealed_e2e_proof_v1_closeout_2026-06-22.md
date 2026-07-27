<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Fresh Sealed E2E Proof v1 Closeout

## Goal

Add a single command surface that attempts a fresh Custom Codex prompt proof,
derives an approved visible Codex-flow projection, runs the full-runtime
dispatch runner, applies strict admission, and seals the result against a
freshness anchor digest. The command must fail closed when the fresh run, UI
visibility proof, admission, seal, or wrong-digest negative check does not pass.

## Result

- status: completed with implementation proof and failed live diagnostic
- final verdict: `codex-runner fresh-sealed-e2e-proof` now exists, writes a
  file-backed final packet, binds a fresh sha256 freshness anchor through
  runner/admission/seal, and refuses final green if the wrong-digest negative
  is unexpectedly accepted.
- closure state: CLOSED

## Contour Capsule

- goal: fresh sealed E2E proof v1
- branch: `codex/stabilize-runtime-core`
- head: `40645a41c1bd4d1845b5238bfcb165ff2a10208e`
- touched files: `wild_boar_proxy/fresh_sealed_e2e_proof.py`, `wild_boar_proxy/cli.py`, `tests/test_fresh_sealed_e2e_proof.py`, `audit_results/fresh_sealed_e2e_proof_v1_closeout_2026-06-22.md`
- tests run: `python3 -m py_compile wild_boar_proxy/fresh_sealed_e2e_proof.py wild_boar_proxy/cli.py`; `python3 -m pytest tests/test_fresh_sealed_e2e_proof.py -q`; `python3 -m pytest tests/test_fresh_sealed_e2e_proof.py tests/test_fresh_live_custom_codex_e2e_proof.py tests/test_custom_codex_visible_source_binding_proof.py tests/test_custom_codex_ui_visibility_proof.py -q`; `python3 -m pytest tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_admission_seal.py -q`; `python3 -m pytest tests/test_cli.py -k 'fresh_sealed or fresh_live or native_ui_observer or full_runtime_dispatch' -q`; `python3 -m compileall -q wild_boar_proxy tests/test_fresh_sealed_e2e_proof.py`; `python3 -m pytest tests/test_cli.py -q`; `make test-core`; live diagnostic command into `/private/tmp/wbp-fresh-sealed-e2e-live-20260622T020000Z`
- blocked risks: replay false-green, wrong freshness digest false-green,
  route/backend detail leakage into approved visible source, product-ready
  overclaim, local DIP imitation, fallback overclaim, raw prompt storage,
  raw provider response storage, native subagent-as-DIP overclaim
- closure state: CLOSED

## Verification

- tests:
  - fresh sealed focused suite: 5 passed
  - fresh sealed plus fresh-live, visible-source, and UI visibility suites: 47 passed, 16 subtests passed
  - full-runtime runner, admission, and seal suites: 39 passed
  - CLI fresh/full-runtime slice: 2 passed, 498 deselected
  - full CLI suite: 500 passed, 123 subtests passed
  - core suite: 418 passed, 120 subtests passed
- build:
  - `python3 -m py_compile wild_boar_proxy/fresh_sealed_e2e_proof.py wild_boar_proxy/cli.py`
  - `python3 -m compileall -q wild_boar_proxy tests/test_fresh_sealed_e2e_proof.py`
- manual:
  - reviewed that the final packet records digests and booleans only, does not
    store the raw prompt, raw route id, raw provider response, raw JSONL, proof
    directory path, or input file paths, and keeps `product_ready=false`.
- live verification:
  - attempted real WBP Custom Codex diagnostic at
    `/private/tmp/wbp-fresh-sealed-e2e-live-20260622T020000Z`.
  - result: final packet `status=error`,
    `machine_error_code=WBP_FRESH_SEALED_E2E_FRESH_LIVE_FAILED`,
    `fresh_sealed_e2e_proven=false`, `fresh_runtime_proof_sealed=false`,
    `product_ready=false`, `fallback_used=false`, `local_imitation_used=false`.
  - root cause observed in `codex-exec.jsonl`: `Missing environment variable:
    OPENAI_API_KEY`.
  - final packet sha256:
    `f4daede2001f948cdba360101b8401d51fc9a88074d8c5fc41c2c842ad80d8da`.
  - fresh-live packet sha256:
    `5979ae76f94bc1d053e3c567fe84021ccdf2554ff1d7272a84afbb84bda9a7b6`.

## Artifacts

- spec: active operator contour instruction in the task thread.
- packet: `/private/tmp/wbp-fresh-sealed-e2e-live-20260622T020000Z/fresh-sealed-e2e-proof.packet.json`
- report: `tests/test_fresh_sealed_e2e_proof.py`

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing UI worktree edits in
  `tests/test_web_design_ui.py` and
  `wild_boar_proxy/web_design_ui/scripts/overview.js` were left unstaged and
  unchanged.
- private-data risk reviewed: yes; the final packet records sha256 values and
  safe booleans, writes no raw prompt, raw route id, raw provider response,
  raw JSONL, or raw backend details, and the approved visible projection drops
  backend command-execution events before UI visibility proof.

## Notes

- blockers encountered: the first implementation attempt fed raw
  `codex-exec.jsonl` into the approved visible-source proof; route secret
  screening correctly blocked that as a backend-detail leak. The command now
  derives a file-backed approved visible projection from the same fresh run
  before UI visibility, full-runtime admission, and seal.
- resume from here: CLOSED
