<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R68 CLI Bundle Production Admission

## Objective

Admit modern Qwen Code and Kimi Code standalone releases without weakening the
deny-default one-shot sandbox or trusting only a thin launcher whose support
tree can drift independently.

## In Scope

- recognize only one first-level package beneath the server-owned admission
  `releases` root as a managed CLI bundle
- bind the launcher identity and the complete bundle tree into admission
  schema V2
- reject unsafe owners/modes, special files, symlink escapes, excessive file
  count/size, and any post-admission bundle drift before operational spawn
- grant the exact bundle root read-only sandbox access while keeping external
  writes and network denied by default
- admit read-only `sysctl` metadata and the macOS `/bin/sh` selector path needed
  by current Node and PyInstaller bootstrap code
- preserve isolated provider homes, secret scrubbing, exact argv, provider
  network gating, process-group termination, and no-resume semantics

## Out of Scope

- provider credentials or login
- real provider dispatch or live evidence
- public release
- ambient package-manager paths or arbitrary caller-selected bundle roots
- UI work

## Constraints

- bundle roots are code-derived, never supplied per request
- bundle read access never implies bundle write access
- the admission record contains only paths, modes, counts, sizes, versions,
  and hashes; it contains no credential values
- a probe grants no operational authority
- any schema or bundle mismatch fails closed before provider-home creation or
  operational spawn

## Assumptions

- current official macOS arm64 Qwen Code releases use a Node/JavaScript bundle
- current official macOS arm64 Kimi Code onedir releases use a PyInstaller
  support tree

## Acceptance Criteria

- [x] official standalone bundle probes can start under the real macOS
      deny-default sandbox
- [x] admission schema V2 records a full bundle-tree SHA-256, file count, and
      byte count alongside the launcher identity
- [x] support-file drift blocks before operational spawn
- [x] symlink escape, unsafe mode/owner, size, and count violations fail closed
- [x] repo reads, external writes, symlink escapes, two-stage writes, and
      default network access remain denied
- [x] README no longer says binary admission itself is an outstanding product
      capability

## Verification

- tests: production admission, real macOS sandbox, and adversarial sandbox
- build: repository compile/check gates
- manual: official checksum verification plus real Qwen/Kimi version probes
- live evidence: none; credentials and provider dispatch remain pending

## Open Questions

- None blocking.
