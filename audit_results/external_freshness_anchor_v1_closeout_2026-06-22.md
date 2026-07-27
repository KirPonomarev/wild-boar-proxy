<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Freshness Anchor v1 Closeout

## Goal

Bind repeatable full-runtime proof evidence to an external sha256 freshness
challenge digest, while preserving the existing runner/admission effect split
and keeping the final full-runtime dispatch proof freshness-agnostic.

## Result

- status: completed
- final verdict: the runner can record a digest-only freshness anchor in its
  packet and manifest, and admission strict mode accepts only a matching
  expected digest while preserving backward-compatible coherence-only admission.
- closure state: CLOSED

## Contour Capsule

- goal: add digest-only external freshness binding to the full-runtime proof runner and admission gate.
- branch: codex/stabilize-runtime-core
- head: e0509520
- touched files: wild_boar_proxy/full_runtime_dispatch_proof_runner.py; wild_boar_proxy/full_runtime_dispatch_admission.py; wild_boar_proxy/cli.py; tests/test_full_runtime_dispatch_proof_runner.py; tests/test_full_runtime_dispatch_admission.py; tests/test_full_runtime_dispatch_proof.py; audit_results/external_freshness_anchor_v1_closeout_2026-06-22.md
- tests run: python3 -m pytest tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_admission.py -q; python3 -m pytest tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof.py -q; python3 -m pytest tests/test_cli.py -k 'full_runtime_dispatch or cli_effect_classifier_covers_canonical_error_contexts' -q; python3 -m compileall -q wild_boar_proxy/full_runtime_dispatch_proof_runner.py wild_boar_proxy/full_runtime_dispatch_admission.py wild_boar_proxy/full_runtime_dispatch_proof.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof.py; git diff --check -- wild_boar_proxy/full_runtime_dispatch_proof_runner.py wild_boar_proxy/full_runtime_dispatch_admission.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof.py; make test-core; python3 -m pytest tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py tests/test_official_e2e_working_flow_proof_runner.py tests/test_official_e2e_fresh_working_flow_proof_runner.py -q; live strict freshness replay into /private/tmp/wbp-full-runtime-freshness-anchor-20260622TYomAyU
- blocked risks: zero unresolved blockers; copied proof_dir evidence with a different expected digest is rejected, while a fully copied proof_dir with the same expected digest remains an operator challenge discipline boundary.
- closure state: CLOSED

## Verification

- tests: runner/admission focused suite passed 27 tests; runner/admission/final
  proof suite passed 38 tests and 4 subtests; proof bundle passed 59 tests and
  4 subtests; CLI focused check passed 2 tests, 81 subtests, and 498 deselected
  tests; make test-core passed 418 tests and 120 subtests.
- build: compileall passed for the touched runtime modules and tests.
- manual: git diff --check passed for the touched implementation and test files.
- live verification: proof_dir
  /private/tmp/wbp-full-runtime-freshness-anchor-20260622TYomAyU used anchor
  digest f830282144c9ebcef546bd72f707611841bb54e2abd3cfac2e5340f8709fff7c;
  runner returned status ok and freshness_anchor_digest_present true while
  external_freshness_proven stayed false; admission with matching expected
  digest returned proof_admitted true, external_freshness_proven true,
  expected_freshness_anchor_digest_bound true, evidence_written false, and
  file_mutation_attempted false.
- tamper verification: admission with wrong expected digest returned status
  error, machine_error_code WBP_FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID,
  proof_admitted false, external_freshness_proven false, and runner/manifest
  freshness digest mismatch reasons.

## Artifacts

- spec: current contour instruction in the active operator thread.
- packet: /private/tmp/wbp-full-runtime-freshness-anchor-20260622TYomAyU/admission.stdout.json
- report: /private/tmp/wbp-full-runtime-freshness-anchor-20260622TYomAyU/admission-wrong.stdout.json

## Git

- branch: codex/stabilize-runtime-core
- commit: not committed at closeout authoring time
- pushed: not pushed at closeout authoring time

## Scope Check

- unrelated work mixed in: no; pre-existing changes in tests/test_web_design_ui.py and wild_boar_proxy/web_design_ui/scripts/overview.js were left unstaged and unchanged.
- private-data risk reviewed: yes; raw anchor input is not accepted, only sha256 digest is accepted, raw_freshness_anchor_recorded remains false, and final full-runtime dispatch proof packets have no freshness fields.

## Notes

- blockers encountered: CLI freshness forwarding initially landed on the wrong
  dispatch branch; a focused test and independent audit caught it, and the final
  proof route now rejects freshness arguments while the runner route forwards
  the digest.
- resume from here: CLOSED
