<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B12_ADMISSION GLM CLI Admission

## Objective

Evaluate GLM CLI admission per the plan: official client, tool, auth,
license, and Coding Plan admission. If not admitted, close GLM as
`API_ONLY` with evidence (a valid terminal result). No GLM CLI code or
live phase runs without admission. The main Codex surface stays forbidden
(owner safety override); the probe never touches `~/.codex` or any Codex
credential store.

## In Scope

- `wild_boar_proxy/glm_cli_admission.py` (new):
  - presence probe for official GLM CLI candidates (`glm`, `zai`,
    `zhipu`, `glm-cli`, `zai-cli`, `zhipu-cli`) via PATH resolution only
  - auth availability check: presence-only; no secret material, no
    credential store access beyond the CLI's own declared surface
  - license / Coding Plan confirmation: verifiable only with an official
    client present; otherwise reported as not confirmed (honest)
  - admission evaluation packet: per-criterion evidence, decision
    (`ADMITTED` | `NOT_ADMITTED`), and terminal result `API_ONLY` when not
    admitted
  - decision rule: ADMITTED only when official client AND auth AND
    license/Coding Plan are all confirmed; anything missing fails closed
- tests: `tests/test_glm_cli_admission.py`
- B12_ADMISSION spec + closeout in `audit_results/`

## Out of Scope

- GLM CLI implementation (B12_CODE_IF_ADMITTED — only when admitted)
- GLM live proof (B12_LIVE_IF_IMPLEMENTED — only when implemented)
- GLM API adapter changes (GLM API already bound in B07_CODE)
- any canon change (no command/state schema touch)

## Constraints

- NOT_ADMITTED is a valid terminal result; GLM then closes as API_ONLY
  with evidence
- the probe resolves PATH candidates only; it never reads `~/.codex`,
  main auth stores, or Codex credentials (owner safety override)
- license / Coding Plan confirmation is never assumed without an official
  client; missing evidence fails closed
- no network calls are made for admission

## Assumptions

- official GLM CLI presence is decided by PATH resolution; absence of an
  official client is the expected honest outcome on this machine unless
  the owner installs one

## Acceptance Criteria

- [ ] presence probe covers the declared candidates and reports facts
- [ ] admission requires official client AND auth AND license/Coding Plan
- [ ] missing any criterion fails closed to NOT_ADMITTED with per-criterion
      evidence
- [ ] terminal result is API_ONLY when not admitted
- [ ] no Codex surface is touched by the probe
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_glm_cli_admission.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (admission is a local deterministic evaluation)

## Open Questions

- None blocking.
