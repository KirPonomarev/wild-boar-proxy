<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60 One-Shot CLI Production Admission Closeout

## Goal

Repair the reopened B09 production gap by replacing the permanently disabled,
empty-manifest facade with an immutable declaration plus exact binary-admission
boundary, without claiming provider-specific Qwen/Kimi readiness.

## Result

- status: code complete with full local verification and remote branch readback
- final verdict: R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: declare complete server-owned Qwen/Kimi policies, admit exact executable identities through a canonical locked store, revalidate every operational dispatch, and close secret/process-boundary defects while provider adapters remain fail-closed
- branch: codex/r60-one-shot-production-admission
- head: 5ac092a063078f1c12ff2d3091d6038a6d8e41ae (implementation head; this closeout is documentation-only)
- touched files: ADR-0004-server-owned-one-shot-cli-admission.md, Makefile, RUNTIME_CONTRACT.md, wild_boar_proxy/one_shot_cli_runtime.py, tests/test_one_shot_cli_production_admission.py, tests/test_one_shot_cli_runtime.py, tests/test_r51_production_test_separation.py, tests/test_r53_hermeticity.py, tests/test_qwen_one_shot_cli.py, tests/test_kimi_one_shot_cli.py, audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_SPEC_2026-08-11.md, audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_closeout_2026-08-11.md
- tests run: 106 focused tests; 630 core tests and 132 subtests; 5066 full-suite tests and 985 subtests; 27 Custom stability tests and 5 subtests; one deterministic temp-root production admission canary
- blocked risks: Qwen/Kimi executables, isolated provider logins, provider-specific argv/output adapters, and provider network permission are absent by design; no live provider readiness is claimed
- closure state: CLOSED

## Verification

- tests: focused one-shot/admission/sandbox suites passed 106 tests in 13.76 seconds; `make test-core` passed 630 tests and 132 subtests in 64.76 seconds; `make test-full` passed 5066 tests and 985 subtests in 1295.12 seconds
- build: `make check` compiled repository Python surfaces and collected 5066 tests; `make test-custom-stability` passed 27 tests and 5 subtests in 2.80 seconds; the only full-suite warning was the pre-existing Pillow `getdata` deprecation
- manual: one deterministic temp-root `/bin/echo` canary proved typed pre-admission blocking, non-authorizing probe, explicit expected-digest admission, canonical atomic storage, `0700` root, `0600` file and real lock, immediate identity revalidation, exact output, and pending Qwen/Kimi adapter codes
- live verification: no Qwen/Kimi executable, credential, login, provider request, network call, or fixed production admission write occurred; the guarded push created the remote branch at exact implementation commit `5ac092a063078f1c12ff2d3091d6038a6d8e41ae`, confirmed by `git ls-remote`

## Artifacts

- spec: `audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_SPEC_2026-08-11.md`
- packet: typed missing/invalid/drifted admission, provider-adapter/auth/network policy, secret-input, probe, admission, and revalidated-run packets exercised by the focused matrix
- report: external execution-state revisions 67 through 70 and immutable transition receipts bind exact-main branch creation, reproduction/spec/ADR, local verification, implementation commit, guarded push, and remote readback

## Git

- branch: codex/r60-one-shot-production-admission
- commit: 5ac092a063078f1c12ff2d3091d6038a6d8e41ae contains the implementation, tests, ADR, runtime contract, core-test selection, and verified spec
- pushed: yes, origin branch read back at the exact implementation commit before this closeout was authored

## Scope Check

- unrelated work mixed in: false; the contour changes only the generic one-shot declaration/admission/runtime boundary, directly affected compatibility tests, the runtime contract, ADR, spec, core-test selection, and closeout
- private-data risk reviewed: no credential values, provider payloads, main Codex profile/auth/session data, protected ports, host network settings, UI, tags, releases, or user-owned canonical-checkout changes were accessed or introduced

## Notes

- blockers encountered: the original production manifest was empty, every production method returned one permanent disabled code, serialized child output could expose secret-shaped values, and timeout handling did not guarantee whole-process-group cleanup; each defect now has a typed regression proof
- resume from here: CLOSED
