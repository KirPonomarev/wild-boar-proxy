<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Proof Admission Seal v1 Closeout

## Goal

Add a read-only machine-verifiable seal verdict for strict full-runtime
dispatch admission evidence, bound to an expected external freshness digest.

## Result

- status: completed
- final verdict: the CLI can produce a read-only seal packet over a strict
  full-runtime dispatch admission packet, with an admission packet digest,
  external freshness binding, no evidence write, and fail-closed handling for
  missing digest, wrong digest, stale proof, unproven admission, unsafe claims,
  and path leakage.
- closure state: CLOSED

## Contour Capsule

- goal: add a read-only full-runtime dispatch admission seal verdict.
- branch: codex/stabilize-runtime-core
- head: 02f451fa
- touched files: wild_boar_proxy/full_runtime_dispatch_admission_seal.py; wild_boar_proxy/cli.py; tests/test_full_runtime_dispatch_admission_seal.py; audit_results/proof_admission_seal_v1_closeout_2026-06-22.md
- tests run: python3 -m pytest tests/test_full_runtime_dispatch_admission_seal.py -q; python3 -m pytest tests/test_full_runtime_dispatch_admission_seal.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py -q; python3 -m pytest tests/test_cli.py -k 'full_runtime_dispatch or cli_effect_classifier_covers_canonical_error_contexts' -q; python3 -m pytest tests/test_full_runtime_dispatch_admission_seal.py tests/test_full_runtime_dispatch_admission.py tests/test_full_runtime_dispatch_proof_runner.py tests/test_full_runtime_dispatch_proof.py tests/test_official_e2e_working_flow_proof_runner.py tests/test_official_e2e_fresh_working_flow_proof_runner.py -q; python3 -m compileall -q wild_boar_proxy/full_runtime_dispatch_admission_seal.py wild_boar_proxy/cli.py tests/test_full_runtime_dispatch_admission_seal.py; make test-core; live seal replay into /private/tmp/wbp-admission-seal-live-final-20260622TjAEQPi
- blocked risks: zero unresolved blockers; unsafe admission claims are classified as WBP_FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE, and wrong or absent freshness digests do not produce a sealed verdict.
- closure state: CLOSED

## Verification

- tests: seal-focused suite passed 9 tests; full-runtime proof/admission suite
  passed 47 tests and 4 subtests; official/full-runtime bundle passed 68 tests
  and 4 subtests; CLI focused check passed 2 tests, 81 subtests, and 498
  deselected tests; make test-core passed 418 tests and 120 subtests.
- build: compileall passed for the touched runtime module, CLI module, and seal
  tests.
- manual: implementation review confirmed the seal command is read-only, calls
  admission only after a valid expected sha256 freshness digest is provided,
  returns no embedded admission payload, and records no proof directory path.
- live verification: proof_dir
  /private/tmp/wbp-admission-seal-live-final-20260622TjAEQPi/proof used freshness
  digest 97563106771ad3d4609b122a11a624162060d414b964ff36a68edf69265a35d1;
  runner returned status ok, machine_error_code OK, and
  freshness_anchor_digest_present true; seal returned status ok,
  machine_error_code OK, proof_admission_sealed true,
  feature_runtime_proof_sealed true, external_freshness_proven true,
  admission_packet_sha256_present true, effect read, evidence_written false,
  and file_mutation_attempted false.
- tamper verification: seal with wrong expected digest returned exit 1, status
  error, machine_error_code WBP_FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED,
  proof_admission_sealed false, and feature_runtime_proof_sealed false.

## Artifacts

- spec: active operator contour instruction in the task thread.
- packet: /private/tmp/wbp-admission-seal-live-final-20260622TjAEQPi/seal.json
- report: /private/tmp/wbp-admission-seal-live-final-20260622TjAEQPi/wrong-seal.json

## Git

- branch: codex/stabilize-runtime-core
- commit: not committed at closeout authoring time
- pushed: not pushed at closeout authoring time

## Scope Check

- unrelated work mixed in: no; pre-existing changes in tests/test_web_design_ui.py and wild_boar_proxy/web_design_ui/scripts/overview.js were left unstaged and unchanged.
- private-data risk reviewed: yes; seal accepts only sha256 freshness digest,
  does not store raw prompt, raw route, raw provider response, raw freshness
  anchor, or proof directory path, and redacts path-like proof_dir values from
  command packets.

## Notes

- blockers encountered: initial secret scanning treated the short test token
  proof as secret material and redacted packet keys; the scanner now treats only
  path-like proof_dir values as packet secret values while preserving real path
  leak detection.
- resume from here: CLOSED
