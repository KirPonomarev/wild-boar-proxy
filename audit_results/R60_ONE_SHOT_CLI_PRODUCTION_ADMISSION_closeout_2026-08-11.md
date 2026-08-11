<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60 One-Shot CLI Production Admission Closeout

## Goal

Repair the reopened B09 production gap by replacing the permanently disabled,
empty-manifest facade with an immutable declaration plus exact binary-admission
boundary, without claiming provider-specific Qwen/Kimi readiness.

## Result

- status: code complete with renewed full local verification after two
  preserved Linux CI portability failures
- final verdict: R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: declare complete server-owned Qwen/Kimi policies, admit exact executable identities through a canonical locked store, revalidate every operational dispatch, and close secret/process-boundary defects while provider adapters remain fail-closed
- branch: codex/r60-one-shot-production-admission
- head: 67b5e1a2c56ba73b62c225eea46d3ae9ee922f1e (final implementation/repair head; this refreshed closeout is documentation-only)
- touched files: ADR-0004-server-owned-one-shot-cli-admission.md, Makefile, RUNTIME_CONTRACT.md, wild_boar_proxy/one_shot_cli_runtime.py, tests/test_one_shot_cli_production_admission.py, tests/test_one_shot_cli_runtime.py, tests/test_r51_production_test_separation.py, tests/test_r53_hermeticity.py, tests/test_qwen_one_shot_cli.py, tests/test_kimi_one_shot_cli.py, audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_SPEC_2026-08-11.md, audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_closeout_2026-08-11.md
- tests run: 106 initial focused tests; 20 focused portability/fail-closed tests after each recovery; final 630 core tests and 132 subtests; final 5066 full-suite tests and 985 subtests; final 27 Custom stability tests and 5 subtests; one deterministic temp-root production admission canary
- blocked risks: Qwen/Kimi executables, isolated provider logins, provider-specific argv/output adapters, and provider network permission are absent by design; no live provider readiness is claimed
- closure state: CLOSED

## Verification

- tests: the initial focused one-shot/admission/sandbox suites passed 106 tests in 13.76 seconds; after the final Linux CI repair, the focused portability plus explicit no-sandbox fail-closed matrix passed 20 tests in 2.65 seconds, `make test-core` passed 630 tests and 132 subtests in 65.72 seconds, and `make test-full` passed 5066 tests and 985 subtests in 1296.91 seconds
- build: after the final repair, `make check` compiled repository Python surfaces and collected 5066 tests; `make test-custom-stability` passed 27 tests and 5 subtests in 2.65 seconds; the only full-suite warning was the pre-existing Pillow `getdata` deprecation
- manual: one deterministic temp-root `/bin/echo` canary proved typed pre-admission blocking, non-authorizing probe, explicit expected-digest admission, canonical atomic storage, `0700` root, `0600` file and real lock, immediate identity revalidation, exact output, and pending Qwen/Kimi adapter codes
- live verification: no Qwen/Kimi executable, credential, login, provider request, network call, or fixed production admission write occurred; the superseded remote candidate `73214abd139471188726904d47642748d3667a2d` was explicitly invalidated after exact-SHA Ubuntu checks reproduced the portability defect

## Delivery Incident and Recovery

- exact failure: superseded implementation run `31459938310` and exact
  candidate runs `31460011138`, `31460039975`, and `31460039988` failed the
  same 11 tests in `tests/test_one_shot_cli_production_admission.py`; the final
  candidate Baseline summary was `11 failed, 619 passed, 132 subtests passed`
- root cause: admission and redaction logic tests invoked the production engine
  on Ubuntu without providing a test-only `sandbox-exec` transport; production
  correctly returned `CLI_UNAVAILABLE_UNSAFE` before spawn
- repair: commit `2caa7634bc56e1f8f62689e1f94599fe2be9c581`
  adds a deterministic test-only passthrough transport for platform-neutral
  policy tests; it does not change runtime code or weaken the production
  sandbox requirement
- guard: the separate no-sandbox test still proves typed fail-closed behavior,
  while the real macOS seatbelt suites continue to exercise actual containment
- reruns: no same-signature rerun was used to conceal the defect; the failed
  candidate was invalidated and replaced only after the repair and a fresh
  complete local verification
- second exact failure: refreshed candidate
  `5eb84a9ac04b3e3d3056ec7e853121fc92306f88` failed push Baseline run
  `31461625268`, PR Baseline run `31461628231`, and PR Release run
  `31461628217` on the same later assertion; the push summary was
  `1 failed, 629 passed, 132 subtests passed`
- second root cause: after the first guard allowed execution to reach the
  canonical-store assertion on Ubuntu, the test compared the admitted realpath
  to literal `/bin/echo`; Ubuntu canonicalizes that path to `/usr/bin/echo`
- second repair: commit
  `67b5e1a2c56ba73b62c225eea46d3ae9ee922f1e` compares the record to
  `os.path.realpath("/bin/echo")`; this is test-only and leaves production
  identity validation unchanged
- second recovery: no failed workflow was rerun; the refreshed candidate was
  invalidated, the failure was preserved, and the entire focused/core/full
  verification set was executed again on the repaired tree

## Artifacts

- spec: `audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_SPEC_2026-08-11.md`
- packet: typed missing/invalid/drifted admission, provider-adapter/auth/network policy, secret-input, probe, admission, and revalidated-run packets exercised by the focused matrix
- report: external execution-state revisions 67 through 79 and immutable transition receipts bind exact-main branch creation, reproduction/spec/ADR, initial verification and delivery, both CI stop diagnoses, both candidate invalidations, both repair commits, and both renewed local verifications

## Git

- branch: codex/r60-one-shot-production-admission
- commits: `5ac092a063078f1c12ff2d3091d6038a6d8e41ae` contains the original implementation; `73214abd139471188726904d47642748d3667a2d` is the invalidated first closeout candidate; `2caa7634bc56e1f8f62689e1f94599fe2be9c581` contains the sandbox-transport test repair; `5eb84a9ac04b3e3d3056ec7e853121fc92306f88` is the invalidated refreshed closeout candidate; `67b5e1a2c56ba73b62c225eea46d3ae9ee922f1e` contains the canonical-realpath test repair
- pushed evidence: the original implementation and invalidated closeout candidate were both read back exactly from origin; refreshed candidate delivery truth is intentionally recorded in the external execution-state receipts rather than inferred from this committed file

## Scope Check

- unrelated work mixed in: false; the contour changes only the generic one-shot declaration/admission/runtime boundary, directly affected compatibility tests, the runtime contract, ADR, spec, core-test selection, and closeout
- private-data risk reviewed: no credential values, provider payloads, main Codex profile/auth/session data, protected ports, host network settings, UI, tags, releases, or user-owned canonical-checkout changes were accessed or introduced

## Notes

- blockers encountered: the original production manifest was empty, every production method returned one permanent disabled code, serialized child output could expose secret-shaped values, timeout handling did not guarantee whole-process-group cleanup, the first candidate lacked a Linux test sandbox transport, and the second candidate assumed a platform-specific `/bin/echo` realpath; each defect now has a typed regression proof
- resume from here: CLOSED
