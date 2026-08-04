<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B10_CODE Qwen One-Shot CLI

## Objective

Implement the isolated Qwen one-shot CLI layer on top of the B09 generic
runtime: `QWEN_HOME` / `QWEN_RUNTIME_DIR` isolation, project-config
denial/admission (`.qwen`, `.env`, extensions, plugins default-denied
unless individually admitted and digested), permission controls
(repo write denied by default), text / repo-read proof, denied-write proof,
and timeout / cancel proof — all via fake-adapter controlled evidence.
Real Qwen CLI binary probe is B10_LIVE scope.

## In Scope

- `wild_boar_proxy/qwen_one_shot_cli.py` (new):
  - Qwen one-shot tool id (`qwen-cli`) resolved through the B09 runtime
  - session setup: `QWEN_HOME` and `QWEN_RUNTIME_DIR` environment
    isolation, provider home 0700, presence-only auth session
  - project-config policy: `.qwen`, `.env`, extensions, plugins are
    default-denied; individual admission requires an explicit
    path + sha256 digest stored in the provider home admissions registry;
    digest mismatch or missing admission fails closed
  - permission policy: repo write denied by default; repo read none by
    default (provider stages choose an admitted read mode)
  - run envelope: qwen environment + output parser wired to
    `one_shot_cli_run` / `parse_cli_output`
  - proofs: text proof, repo-read proof (admitted path + digest), denied-
    write proof (policy-level, honest about OS enforcement), timeout proof,
    cancel proof
  - every packet states `resume_supported: false`
- tests: `tests/test_qwen_one_shot_cli.py`
- B10_CODE spec + closeout in `audit_results/`

## Out of Scope

- live Qwen CLI binary probe with credentials (B10_LIVE)
- Kimi one-shot CLI (B11)
- GLM CLI (B12)
- workflow runner (B13)
- any canon change (no command/state schema touch)

## Constraints

- project configs are default-denied; admission is per-path with a digest,
  stored server-side in the provider home; no digest, no admission
- repo write is denied by policy; the denied-write proof never claims OS
  sandbox enforcement when it is absent
- QWEN_HOME / QWEN_RUNTIME_DIR always point inside the isolated provider
  home; the real user home is never the qwen home
- one-shot sessions never resume
- fake-adapter evidence is declared-not-live

## Assumptions

- the qwen CLI (real binary) is not present in the CODE phase; all B10_CODE
  evidence is fake-adapter controlled, and B10_LIVE is the credential-gated
  seam for the real binary

## Acceptance Criteria

- [ ] session setup creates QWEN_HOME + QWEN_RUNTIME_DIR isolation and a
      presence-only auth session
- [ ] project configs are default-denied; admission requires path + digest;
      digest mismatch fails closed
- [ ] permission policy denies repo write by default
- [ ] text proof and repo-read proof (admitted path + digest) via fake
      adapter
- [ ] denied-write proof is policy-level and honest about OS enforcement
- [ ] timeout and cancel proofs terminate the whole process group
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_qwen_one_shot_cli.py` (+ B09 runtime tests);
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (fake-adapter only; B10_LIVE pending credentials)

## Open Questions

- None blocking.
