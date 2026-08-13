<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R68 CLI Bundle Production Admission Closeout

## Goal

Close the production gap between an exact executable admission and the
multi-file standalone bundles required by current Qwen Code and Kimi Code.

## Result

- status: implemented and locally verified
- final verdict: managed standalone bundles are now fully digest-bound,
  sandbox-readable but not writable, and rejected on any support-tree drift
- Qwen Code 0.21.11 and Kimi Code 1.49.0 official macOS arm64 archives were
  independently checksum-verified and probed successfully under the real
  production sandbox
- exact bundle admissions were written with no credentials, provider calls,
  login, or public-release authority
- closure state: CLOSED

## Contour Capsule

- goal: checksum-bound production admission for multi-file Qwen/Kimi releases
- branch: `codex/r68-cli-bundle-production-admission`
- head: exact base `bc90744efd0d604d52da67f9f55d295e1c5040c4` plus the logically complete R68 contour commit
- touched files: one-shot runtime, admission/sandbox tests, README, this spec,
  and this closeout
- tests run: 119 affected one-shot runtime, production-admission, provider
  adapter, and real/adversarial macOS sandbox tests; exact official bundle
  probes for Qwen and Kimi
- blocked risks: launcher-only false admission, mutable support tree, symlink
  escape, over-broad package-manager access, bootstrap failure, unintended
  network/write authority, credential promotion
- closure state: CLOSED

## Verification

- affected one-shot runtime/admission/provider/sandbox matrix: `119 tests`, all
  passed
- `make check`: compileall passed; `5118 tests collected`
- real Qwen Code sandbox probe: `0.21.11`, `status=ok`
- real Kimi Code sandbox probe: `kimi, version 1.49.0`, `status=ok`
- Qwen archive SHA-256 matched official release metadata:
  `ca893e6b236c423473adee97d624b63809a15d20940adbecb5a93a0ff3b4a52e`
- Kimi archive SHA-256 matched official release metadata:
  `3533d7197a3cf807d7ba3b67d54637180544565f6277870f9bcf639ef21754fb`
- admission readback: two admitted tools, schema V2, runtime grant false,
  operational candidate list empty until isolated auth exists
- `git diff --check`: passed

## Artifacts

- spec: `audit_results/R68_CLI_BUNDLE_PRODUCTION_ADMISSION_SPEC_2026-08-13.md`
- packet: server-owned admission readback with launcher and bundle digests
- report: this closeout

## Git

- branch: `codex/r68-cli-bundle-production-admission`
- commit: this logically complete contour commit
- pushed: delivery evidence is recorded externally after exact remote readback

## Scope Check

- unrelated work mixed in: no
- runtime mutation: bounded to server-owned CLI release, admission, and empty
  isolated-home surfaces
- credential values read or persisted: no
- provider network call or live dispatch: no
- primary Codex paths read or changed: no
- public release or protected-network action: no
- private-data risk reviewed: yes; repository artifacts contain only public
  upstream versions/checksums and no private paths or credentials

## Notes

- blockers encountered: current standalone launchers require read-only support
  trees and `sysctl` bootstrap metadata; both were localized with real sandbox
  probes and covered by fail-closed regression tests
- resume from here: CLOSED
