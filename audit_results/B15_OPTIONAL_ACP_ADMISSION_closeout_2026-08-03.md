<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B15_OPTIONAL Persistent ACP Admission Closeout

## Goal

Perform the physical protocol admission for the optional persistent ACP
(Agent Client Protocol) surface. If the protocol is unavailable or
unstable, close as `OPTIONAL_DEFERRED_ACP` with evidence.

## Result

- status: implemented and verified
- final verdict: `optional_acp_admission.py` probes physical ACP
  availability (declared binary candidates via PATH resolution plus
  repository runtime presence) with no network calls and no credential
  stores touched; on this machine no ACP binary is present and the
  repository carries only the `cli_acp` transport-kind enum with no
  runtime implementation, so the decision is `OPTIONAL_DEFERRED_ACP`
  (terminal) with per-criterion evidence
- closure state: CLOSED

## Contour Capsule

- goal: B15_OPTIONAL persistent ACP admission
- branch: `codex/b15-optional-acp-admission`
- head: `f5dfb3f57187c61dfe90ac709d8ebed92117dbfd` (base before contour commit)
- touched files: `wild_boar_proxy/optional_acp_admission.py` (new),
  `tests/test_optional_acp_admission.py` (new),
  `audit_results/B15_OPTIONAL_ACP_ADMISSION_SPEC_2026-08-03.md`,
  `audit_results/B15_OPTIONAL_ACP_ADMISSION_closeout_2026-08-03.md`
- tests run: `tests/test_optional_acp_admission.py` (5); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: assuming admission, network calls during the probe,
  credential-store touches
- closure state: CLOSED (OPTIONAL_DEFERRED_ACP terminal)

## Verification

- tests:
  - `tests/test_optional_acp_admission.py` -> `5 passed` (probe reports
    facts with no network and no credential stores; probe finds declared
    candidates; admission defers without a repository runtime; admission
    defers on this machine; packet never contains secrets)
  - real-machine probe: no ACP binary found, no runtime implemented ->
    `OPTIONAL_DEFERRED_ACP`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - `evaluate_optional_acp()` on this machine -> OPTIONAL_DEFERRED_ACP
    (recorded above)
- live verification:
  - none; local deterministic admission with no network calls

## Artifacts

- spec: `audit_results/B15_OPTIONAL_ACP_ADMISSION_SPEC_2026-08-03.md`
- packet: `evaluate_optional_acp()` packet (OPTIONAL_DEFERRED_ACP)
- report: ACP is deferred; it does not substitute for one-shot acceptance
  (B10/B11 closed)

## Git

- branch: `codex/b15-optional-acp-admission`
- commit: contour commit contains the admission module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (PATH-only probe; no credential stores;
  no secrets in packets)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: one GitHub CI job
  (`make check + test-core + test-custom-stability`) failed once on the
  known timing-sensitive web-e2e test
  `test_http_sandbox_readonly_endpoints_follow_sandbox_target`
  (HTTP TimeoutError on the CI runner; passes locally 3/3 and passed on
  the rerun — same proven CI-runner timing flake pattern documented in
  B13); unrelated to this contour (no web-surface changes)
- resume from here: CLOSED
