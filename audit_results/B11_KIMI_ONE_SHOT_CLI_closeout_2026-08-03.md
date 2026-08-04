<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B11_CODE Kimi One-Shot CLI Closeout

## Goal

Implement the isolated Kimi one-shot CLI layer: `KIMI_CODE_HOME`
isolation, immutable-snapshot repo-read enforcement (OS read-only sandbox
or immutable snapshot is required for `repo_read`; otherwise Kimi is
limited to `none`), text / repo-read proof where safe, denied-write proof,
auth isolation, output normalization, and timeout / cancel proof — via
fake-adapter controlled evidence. Real Kimi CLI binary probe is B11_LIVE
scope.

## Result

- status: implemented and verified
- final verdict: `kimi_one_shot_cli.py` provides the Kimi one-shot layer:
  sessions create a 0700 provider home with `KIMI_CODE_HOME` pointing
  inside it and a presence-only auth session; immutable snapshots are
  server-owned read-only copies (files 0444, dirs 0555, bounded by file
  count and total size, vcs dirs excluded); repo-read policy is
  `immutable_snapshot` with a snapshot and `none` otherwise — Kimi never
  claims an absent OS sandbox; repo-read proof reads only snapshot paths;
  denied-write proof shows a real OS EACCES (errno 13) on a snapshot file,
  never a policy-only claim; text proof, output normalization, timeout /
  cancel proofs are fake-adapter controlled and declared-not-live; one-shot
  sessions never resume
- closure state: CLOSED

## Contour Capsule

- goal: B11_CODE Kimi one-shot CLI layer
- branch: `codex/b11-kimi-one-shot-cli`
- head: `532a5bba3ab22e3b079d9082eed55ef2989aa48e` (base before contour commit)
- touched files: `wild_boar_proxy/kimi_one_shot_cli.py` (new),
  `tests/test_kimi_one_shot_cli.py` (new),
  `audit_results/B11_KIMI_ONE_SHOT_CLI_SPEC_2026-08-03.md`,
  `audit_results/B11_KIMI_ONE_SHOT_CLI_closeout_2026-08-03.md`
- tests run: `tests/test_kimi_one_shot_cli.py` (14);
  `tests/test_one_shot_cli_runtime.py` + `tests/test_qwen_one_shot_cli.py`
  (regression); `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- blocked risks: repo read without OS sandbox or snapshot, writable
  snapshot files (fake denied-write), read outside the snapshot, resume
  support for one-shot sessions, unbounded snapshots
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_kimi_one_shot_cli.py` -> `14 passed` (KIMI_CODE_HOME
    isolation with auth presence; kimi env points inside the provider
    home; snapshot immutable 0444/0555, vcs excluded, bounded; oversize
    fails closed; repo-read policy none without snapshot and
    immutable_snapshot with; read outside snapshot denied; repo-read proof
    matches snapshot content and digest; denied-write proof observes real
    EACCES errno 13; text proof; parsed output; timeout proof; cancel
    proof; fail-closed without session; declared-not-live receipt)
  - B09/B10 regression (`test_one_shot_cli_runtime.py`,
    `test_qwen_one_shot_cli.py`) -> green
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - n/a
- live verification:
  - fake-adapter controlled evidence only
    (`declared_not_live_verified=true`); B11_LIVE is the credential-gated
    seam for the real Kimi CLI binary

## Artifacts

- spec: `audit_results/B11_KIMI_ONE_SHOT_CLI_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: Kimi repo read is admitted only via the immutable snapshot in
  B11_CODE; OS sandbox availability is probed and reported, never assumed

## Git

- branch: `codex/b11-kimi-one-shot-cli`
- commit: contour commit contains the kimi one-shot layer, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (snapshots are server-owned copies under
  the homes root; auth sessions presence-only; secret values never appear
  in packets)
- live-path mutation performed: no (fake-adapter evidence only)
- shared-helper refactor introduced: no (B09 runtime reused as-is)
- materialization output drift accepted: no

## Notes

- blockers encountered: none (14/14 tests passed on first run)
- resume from here: CLOSED
