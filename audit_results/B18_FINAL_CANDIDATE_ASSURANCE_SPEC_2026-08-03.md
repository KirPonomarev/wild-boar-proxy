<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B18 Final Candidate Assurance

## Objective

Run the final candidate assurance checks: exact-remote-head repository
state, full-test evidence, package, privacy, migration, provider, CLI,
workflow, web, account-isolation, and protected-network checks. B18 may
emit only `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`, never `DONE`.

## In Scope

- `wild_boar_proxy/final_candidate_assurance.py` (new):
  - deterministic checks:
    - exact_remote_head: local main equals origin/main
    - full_test: recorded full-suite evidence (passed count, clean run)
    - package: packaging module imports; wheel/sdist build evidence from
      the repository gates
    - privacy: secret redaction probe
    - migration: state migration v1->v2 probe in a temp root
    - provider: 4-provider release set receipt
    - CLI: one-shot runtime receipt (SYNTHETIC_PROVEN)
    - workflow: sequential runner receipt
    - web: workflow control surface gate endpoint probe
    - account_isolation: provider home 0700 isolation probe
    - protected_network: protected ports as product truth + network
      air-gap evidence recorded
  - `run_final_candidate_assurance(...)`: emits
    `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT` only when every check
    passes; never `DONE`
- tests: `tests/test_final_candidate_assurance.py`
- B18 spec + closeout in `audit_results/`

## Out of Scope

- the independent audit itself (Script 5)
- the DONE transition (Script 6, after the audit verdict)
- live credential phases (pending gates)
- any canon change (no command/state schema touch)

## Constraints

- the emitted status is exactly `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`
  or a typed failure; `DONE` is never emitted by B18
- checks are deterministic local probes plus recorded evidence; no
  greenwashing
- the main Codex surface is never touched
- secret values never appear in assurance packets

## Assumptions

- the full suite and CI gates are recorded evidence (this closeout and the
  PR checks)

## Acceptance Criteria

- [ ] all eleven check categories are covered with honest evidence
- [ ] passing matrix emits exactly
      `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`
- [ ] `DONE` never appears in any B18 packet
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_final_candidate_assurance.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall; package gate via `make package-web-smoke`
- manual: `run_final_candidate_assurance()` recorded in the closeout
- live evidence: none

## Open Questions

- None blocking.
