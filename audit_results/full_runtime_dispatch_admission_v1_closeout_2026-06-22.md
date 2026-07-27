<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Full Runtime Dispatch Admission v1 Closeout

## Goal

Add a read-only admission gate that verifies an existing full-runtime proof
directory from disk, admits only coherent file-backed evidence, and rejects
tampered, missing, corrupted, unsafe, or unproven proof artifacts.

## Result

- status: completed
- final verdict: full-runtime dispatch admission is implemented, CLI-routable as
  a read command, and verified against positive, missing, corrupted, hash
  mismatch, post-write tamper, unsafe, and unproven cases.
- closure state: CLOSED

## Contour Capsule

- goal: add a read-only full-runtime dispatch admission gate over proof_dir artifacts.
- branch: codex/stabilize-runtime-core
- head: 5555dd60
- touched files: wild_boar_proxy/full_runtime_dispatch_admission.py; wild_boar_proxy/cli.py; tests/test_full_runtime_dispatch_admission.py; audit_results/full_runtime_dispatch_admission_v1_closeout_2026-06-22.md
- tests run: python3 -m pytest tests/test_full_runtime_dispatch_admission.py -q; python3 -m pytest tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py -q; python3 -m pytest tests/test_cli.py -k 'full_runtime_dispatch or cli_effect_classifier_covers_canonical_error_contexts' -q; python3 -m compileall -q wild_boar_proxy/full_runtime_dispatch_admission.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_admission.py; git diff --check -- wild_boar_proxy/full_runtime_dispatch_admission.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_admission.py; make test-core; python3 -m pytest tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py tests/test_official_e2e_working_flow_proof_runner.py tests/test_official_e2e_fresh_working_flow_proof_runner.py -q; live admission replay into /private/tmp/wbp-full-runtime-admission-20260622T6PzeOT plus tamper replay into /private/tmp/wbp-full-runtime-admission-tamper-20260622T8OOSkY
- blocked risks: no unresolved blockers; absolute anti-replay for a fully copied internally coherent old proof set is not claimed without an external freshness anchor.
- closure state: CLOSED

## Verification

- tests: admission focused suite passed 10 tests; proof-focused bundle passed
  47 tests and 4 subtests; CLI focused check passed 2 tests, 81 subtests, and
  498 deselected tests; make test-core passed 418 tests and 120 subtests.
- build: compileall passed for the admission module, CLI, and admission tests.
- manual: git diff --check passed for the touched implementation and test files.
- live verification: good proof_dir
  /private/tmp/wbp-full-runtime-admission-20260622T6PzeOT returned status ok,
  machine_error_code OK, proof_admitted true, effect read, evidence_written
  false, file_mutation_attempted false, and empty blocking_reasons.
- tamper verification: tampered proof_dir
  /private/tmp/wbp-full-runtime-admission-tamper-20260622T8OOSkY returned
  status error, machine_error_code
  WBP_FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID, proof_admitted false,
  and SHA mismatch blocking reasons.

## Artifacts

- spec: current contour instruction in the active operator thread.
- packet: /private/tmp/wbp-full-runtime-admission-20260622T6PzeOT/admission.stdout.json
- report: /private/tmp/wbp-full-runtime-admission-tamper-20260622T8OOSkY/admission-tamper.stdout.json

## Git

- branch: codex/stabilize-runtime-core
- commit: not committed at closeout authoring time
- pushed: not pushed at closeout authoring time

## Scope Check

- unrelated work mixed in: no; pre-existing changes in tests/test_web_design_ui.py and wild_boar_proxy/web_design_ui/scripts/overview.js were left unstaged and unchanged.
- private-data risk reviewed: yes; admission packet redacts proof_dir path, does not include artifact payloads, and tests reject raw prompt, route id, provider text, backend detail, and product-ready overclaim.

## Notes

- blockers encountered: stale replay of a fully copied coherent old proof set
  cannot be distinguished by this read-only gate without an external freshness
  anchor; the packet therefore admits coherence of the supplied file-backed run
  and does not claim product readiness.
- resume from here: CLOSED
