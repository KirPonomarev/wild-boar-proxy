<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B12_ADMISSION GLM CLI Admission Closeout

## Goal

Evaluate GLM CLI admission per the plan: official client, tool, auth,
license, and Coding Plan admission. If not admitted, close GLM as
`API_ONLY` with evidence (a valid terminal result). No GLM CLI code or live
phase runs without admission. The main Codex surface stays forbidden
(owner safety override).

## Result

- status: implemented and verified
- final verdict: `glm_cli_admission.py` evaluates admission from local
  facts only (PATH resolution for the declared candidate set `glm`, `zai`,
  `zhipu`, `glm-cli`, `zai-cli`, `zhipu-cli`); on this machine no official
  GLM CLI is present, auth / license / Coding Plan are not confirmable, so
  the decision is `NOT_ADMITTED` with terminal result `API_ONLY` —
  B12_CODE_IF_ADMITTED and B12_LIVE_IF_IMPLEMENTED are not executed; GLM
  remains bound through the API adapter (B07_CODE)
- closure state: CLOSED
  (terminal result: API_ONLY — GLM CLI not admitted)

## Contour Capsule

- goal: B12_ADMISSION GLM CLI admission evaluation
- branch: `codex/b12-glm-cli-admission`
- head: `64daff483e4d42f00f4ad69ade5a0216bc9fe316` (base before contour commit)
- touched files: `wild_boar_proxy/glm_cli_admission.py` (new),
  `tests/test_glm_cli_admission.py` (new),
  `audit_results/B12_GLM_CLI_ADMISSION_SPEC_2026-08-03.md`,
  `audit_results/B12_GLM_CLI_ADMISSION_closeout_2026-08-03.md`
- tests run: `tests/test_glm_cli_admission.py` (5); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: assuming admission from client presence alone, touching
  the Codex surface, secret leakage in admission packets, network calls
  during admission
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_glm_cli_admission.py` -> `5 passed` (probe reports
    candidates and no Codex touch; probe finds an official-looking
    candidate in PATH; admission fails closed without client; admission
    still requires auth/license/Coding Plan even with a client present;
    admission packet never contains secrets or `.codex` references)
  - real-machine probe: no official GLM CLI candidate found
    (`found_candidates: {}`) -> `NOT_ADMITTED` / `API_ONLY` /
    `GLM_CLI_ADMISSION_DENIED`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - `evaluate_glm_cli_admission()` on this machine -> NOT_ADMITTED,
    API_ONLY (recorded above)
- live verification:
  - none; admission is a local deterministic evaluation with no network
    calls

## Artifacts

- spec: `audit_results/B12_GLM_CLI_ADMISSION_SPEC_2026-08-03.md`
- packet: `evaluate_glm_cli_admission()` packet (NOT_ADMITTED, API_ONLY)
- report: GLM closes as API_ONLY per plan; B12_CODE_IF_ADMITTED and
  B12_LIVE_IF_IMPLEMENTED are skipped by the conditional

## Git

- branch: `codex/b12-glm-cli-admission`
- commit: contour commit contains the admission module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (PATH-only probe; no Codex surface, no
  credential stores, no secret material in packets)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none
- resume from here: CLOSED
