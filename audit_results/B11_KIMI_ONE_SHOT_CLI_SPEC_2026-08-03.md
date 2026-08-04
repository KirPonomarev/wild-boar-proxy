<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B11_CODE Kimi One-Shot CLI

## Objective

Implement the isolated Kimi one-shot CLI layer: `KIMI_CODE_HOME`
isolation, immutable-snapshot repo-read enforcement (OS read-only sandbox
or immutable snapshot is required for `repo_read`; otherwise Kimi is
limited to `none` or `context_only`), text / repo-read proof where safe,
denied-write proof, auth isolation, output normalization, and timeout /
cancel proof — via fake-adapter controlled evidence. Real Kimi CLI binary
probe is B11_LIVE scope.

## In Scope

- `wild_boar_proxy/kimi_one_shot_cli.py` (new):
  - Kimi one-shot tool id (`kimi-cli`) resolved through the B09 runtime
  - session setup: `KIMI_CODE_HOME` isolation, provider home 0700,
    presence-only auth session (auth isolation)
  - immutable snapshot: server-owned read-only copy of the project (files
    chmod 0444, dirs 0555, bounded size/file count, vcs dirs excluded);
    snapshot creation is honest about failure
  - repo-read policy: `immutable_snapshot` when a snapshot exists,
    otherwise `none` (Kimi never claims an absent OS sandbox); repo-read
    proof reads only snapshot paths
  - denied-write proof: OS-level EACCES on a snapshot file is the evidence
    (never a policy-only claim); OS sandbox availability is probed and
    reported honestly
  - output normalization via the generic parser; timeout / cancel proofs;
    every packet states `resume_supported: false`
- tests: `tests/test_kimi_one_shot_cli.py`
- B11_CODE spec + closeout in `audit_results/`

## Out of Scope

- live Kimi CLI binary probe with credentials (B11_LIVE)
- Qwen one-shot CLI (B10, closed)
- GLM CLI (B12)
- workflow runner (B13)
- any canon change (no command/state schema touch)

## Constraints

- repo read for Kimi requires an OS read-only sandbox or an immutable
  snapshot; with neither, Kimi is limited to `none`/`context_only`
- snapshot files are OS read-only (0444); writes to them must fail with a
  real EACCES, which is the denied-write evidence
- KIMI_CODE_HOME always points inside the isolated provider home
- one-shot sessions never resume
- fake-adapter evidence is declared-not-live

## Assumptions

- the Kimi CLI (real binary) is not present in the CODE phase; all B11_CODE
  evidence is fake-adapter controlled; B11_LIVE is the credential-gated
  seam

## Acceptance Criteria

- [ ] session setup creates KIMI_CODE_HOME isolation + presence-only auth
      session
- [ ] immutable snapshot creation is bounded, read-only (0444/0555), and
      honest about failure
- [ ] repo-read policy is `immutable_snapshot` with a snapshot, `none`
      otherwise; repo-read proof reads only snapshot paths
- [ ] denied-write proof shows a real OS EACCES on a snapshot file
- [ ] text proof and output normalization via fake adapter
- [ ] timeout and cancel proofs terminate the whole process group
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_kimi_one_shot_cli.py` (+ B09/B10 regression);
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none (fake-adapter only; B11_LIVE pending credentials)

## Open Questions

- None blocking.
