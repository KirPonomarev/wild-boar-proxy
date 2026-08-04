<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B00_REOPEN: Audit-Driven P0/P1 Repair Closeout

## Goal

Fix the P0/P1 findings from the external independent audit
(FAIL_REOPEN_STAGE_B00): permission intersection capability-set,
sterile env scrub, sandbox enforcement, ledger path containment,
binding_id uniqueness, API adapter live dispatch, design gate honest
checks, canon digest transition recording, and evidence-index field
normalization.

## Result

- status: implemented and verified
- final verdict: all eight confirmed P0/P1 findings reproduced and
  repaired with regression tests; canon digest transition recorded;
  evidence-index normalized (receipt_digest + observed_at for all refs);
  9 audit-driven regression tests pass; state reopened from
  FAIL_REOPEN_STAGE_B00 to IN_PROGRESS for continued repair
- closure state: CLOSED

## Contour Capsule

- goal: B00_REOPEN audit-driven P0/P1 repair
- branch: `codex/b00-reopen-audit-repair`
- head: `692501f3ac09517f41bbdd2ac462bd5d85892ee6` (base)
- touched files: `wild_boar_proxy/actor_dispatcher.py`,
  `wild_boar_proxy/one_shot_cli_runtime.py`,
  `wild_boar_proxy/thread_context_ledger.py`,
  `wild_boar_proxy/actor_registry.py`,
  `wild_boar_proxy/execution_core_design_gate.py`,
  `wild_boar_proxy/api_transport_adapter.py`,
  `wild_boar_proxy/final_candidate_assurance.py`,
  `tests/test_actor_dispatcher.py`,
  `tests/test_audit_regression_p0.py` (new),
  `audit_results/B00_REOPEN_audit_repair_closeout_2026-08-04.md`
- tests run: `tests/test_audit_regression_p0.py` (9);
  `tests/test_actor_dispatcher.py` (20); `tests/test_one_shot_cli_runtime.py`;
  `tests/test_execution_core_design_gate.py`;
  `tests/test_thread_context_ledger.py`;
  `tests/test_security_reliability_matrix.py`;
  `tests/test_final_candidate_assurance.py`;
  `tests/test_web_workflow_control.py`;
  `tests/test_api_transport_adapter.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- blocked risks: all P0/P1 findings from the external audit
- closure state: CLOSED

## Findings Repaired

1. **[P0] Permission intersection** — replaced linear rank with
   capability-set intersection; `network_read` grant no longer yields
   `repo_write` (returns `context_only`)
2. **[P0] Sterile env** — added FORBIDDEN_ENV_KEYS scrubbing
   (`CODEX_HOME`, `WBP_PROFILE_DIR`, `SSH_AUTH_SOCK`, proxy vars,
   keyring/editor)
3. **[P0] Sandbox enforcement** — read-only temp cwd (chmod 0555) when
   `repo_write=denied`; child writes blocked by OS EACCES, not just
   policy claim
4. **[P0] Ledger path containment** — `Path.resolve().relative_to()`
   replaces `str.startswith()`; `../approved-escape` blocked
5. **[P0] binding_id uniqueness** — registry validation rejects
   duplicate `binding_id` across slot_bindings
6. **[P0] API adapter live dispatch** — `_provider_headers` now receives
   `ExternalModelsPaths`; `_dispatch_success_packet` called with named
   args (not kwargs-splat)
7. **[P1] Design gate honest checks** — validates 40-hex git SHA +
   known stage IDs; fake stages/bad SHA no longer earn the token
8. **[P0] Canon digest transition** — `a2a482…→dfd113…` recorded;
   evidence-index normalized (`receipt_digest` + `observed_at` for all
   21 refs)

## Verification

- tests:
  - `tests/test_audit_regression_p0.py` -> `9 passed` (each test
    reproduces a specific audit finding and asserts the fix)
  - affected modules (8 test files) -> `162 passed`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
- build:
  - `make check` (compileall + collect) green
- manual:
  - negative probes from the audit reproduced before fix, pass after fix
- live verification:
  - none (code repair; live gates remain pending)

## Artifacts

- spec: this closeout (inline scope — B00_REOPEN from external audit)
- packet: no live packet artifact
- report: external audit FAIL_REOPEN_STAGE_B00 findings 1–8 repaired;
  remaining audit items (production manifests, Lazyweb pass, web
  integration, B00 ancestry, package version) are subsequent repair
  contours

## Git

- branch: `codex/b00-reopen-audit-repair`
- commit: contour commit contains all P0/P1 fixes + regression tests
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (sandbox enforcement prevents child
  writes; sterile env prevents Codex/proxy leakage)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: the original test suite passed while all P0 bugs
  were present — the tests encoded the buggy contract; the new
  `test_audit_regression_p0.py` closes the greenwash gap by testing the
  actual safety boundary, not the internal contract
- resume from here: CLOSED
