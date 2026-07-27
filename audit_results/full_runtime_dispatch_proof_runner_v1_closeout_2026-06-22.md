<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Full Runtime Dispatch Proof Runner v1 Closeout

## Goal

Build a repeatable file-backed runner that reconstructs the Custom Codex
UserPromptSubmit-to-API-dispatch proof chain from existing evidence files,
writes deterministic proof artifacts, and refuses false-positive success when
required inputs, chain joins, or artifact writes fail.

## Result

- status: completed
- final verdict: repeatable full runtime dispatch proof runner is implemented,
  CLI-routable, classified as mutate, and verified against positive, negative,
  write-failure, and live replay scenarios.
- closure state: CLOSED

## Contour Capsule

- goal: add a repeatable full runtime dispatch proof runner with file-backed manifest and fail-closed verification.
- branch: codex/stabilize-runtime-core
- head: 144d5889
- touched files: wild_boar_proxy/full_runtime_dispatch_proof_runner.py; wild_boar_proxy/cli.py; tests/test_full_runtime_dispatch_proof_runner.py; audit_results/full_runtime_dispatch_proof_runner_v1_closeout_2026-06-22.md
- tests run: python3 -m pytest tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py tests/test_official_e2e_working_flow_proof_runner.py tests/test_official_e2e_fresh_working_flow_proof_runner.py -q; python3 -m pytest tests/test_cli.py -k 'full_runtime_dispatch or cli_effect_classifier_covers_canonical_error_contexts' -q; python3 -m compileall -q wild_boar_proxy/full_runtime_dispatch_proof_runner.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_proof_runner.py; git diff --check -- wild_boar_proxy/full_runtime_dispatch_proof_runner.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_proof_runner.py; make test-core; live CLI replay into /private/tmp/wbp-full-runtime-dispatch-proof-runner-20260622TjhsTeo
- blocked risks: no unresolved blockers; proof_dir absence, artifact write failure, missing JSONL, UI handoff mismatch, malformed visibility counts, and unproven API dispatch source are covered by fail-closed tests.
- closure state: CLOSED

## Verification

- tests: 37 pytest cases plus 4 subtests passed for the runner and adjacent
  proof chain tests; CLI focused check passed 2 tests, 81 subtests, and 498
  deselected tests; make test-core passed 418 tests and 120 subtests.
- build: compileall passed for the new runner, CLI, and runner tests.
- manual: git diff --check passed for the touched implementation and test files.
- live verification: CLI replay wrote 11 JSON artifacts under
  /private/tmp/wbp-full-runtime-dispatch-proof-runner-20260622TjhsTeo with
  status ok, machine_error_code OK, full_runtime_dispatch_runner_proven true,
  full_runtime_dispatch_proven true, evidence_written true, and empty
  blocking_reasons.

## Artifacts

- spec: current contour instruction in the active operator thread.
- packet: /private/tmp/wbp-full-runtime-dispatch-proof-runner-20260622TjhsTeo/full-runtime-dispatch-proof-runner.packet.json
- report: /private/tmp/wbp-full-runtime-dispatch-proof-runner-20260622TjhsTeo/full-runtime-dispatch-proof-runner-manifest.json

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; pre-existing changes in tests/test_web_design_ui.py and wild_boar_proxy/web_design_ui/scripts/overview.js were left unstaged and unchanged.
- private-data risk reviewed: yes; tests inspect written JSON artifacts for raw prompt, route, provider text, expected text, and temporary root path leaks.

## Notes

- blockers encountered: initial artifact write flags could overclaim evidence
  when proof_dir was absent or writes failed; regression tests now cover those
  cases and the runner reports artifact-write failure instead of success.
- resume from here: CLOSED
