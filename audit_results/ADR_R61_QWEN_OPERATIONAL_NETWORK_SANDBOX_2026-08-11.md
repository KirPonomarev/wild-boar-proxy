<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Qwen Operational Network Sandbox

## Status

Accepted

## Date

2026-08-11

## Context

The generic B09 one-shot runtime is intentionally offline. A real Qwen Code
response requires provider network access, but widening the shared sandbox or
the sterile binary probe would silently enlarge every one-shot trust boundary.
This decision is expensive to reverse because it controls provider egress,
credential-bearing process isolation, and repo read/write containment.

## Decision

Keep the default and sterile-probe profile offline. Add one explicit
server-owned provider-network profile selected only by the production facade
after Qwen adapter admission, exact binary admission and revalidation, and
isolated-home auth-presence validation. The operational child may use outbound
network, may read an explicitly validated active-project root, may write only
its sealed provider home and ephemeral sandbox directory, and may never receive
caller argv, caller environment, writable repo access, or resume authority.

## Alternatives Considered

1. Allow network in the shared default profile
   Rejected because probes, Kimi, tests, and any future tool would inherit an
   unnecessary egress path.
2. Keep Qwen permanently offline
   Rejected because code could never reach B10 live acceptance and the
   production adapter would remain a structural false green.
3. Trust Qwen Code `--safe-mode` without OS enforcement
   Rejected because safe mode disables customization but is not a host
   filesystem or network sandbox.

## Consequences

- Positive: offline remains the default; network widening is exact,
  declaration-bound, revalidated, and testable.
- Negative: macOS seatbelt cannot restrict outbound traffic by provider
  hostname, so live admission must treat provider egress as a broad outbound
  capability inside the otherwise narrow child sandbox.
- Follow-up work: B10_LIVE must bind an installed binary and isolated auth
  configuration, then prove positive text/repo-read, denied write,
  timeout/cancel, redaction, and no protected host mutation.

## Evidence

- spec: `audit_results/R61_QWEN_ONE_SHOT_PRODUCTION_ADAPTER_SPEC_2026-08-11.md`
- tests: focused runtime, Qwen production adapter, and real macOS seatbelt
  network/read/write canaries
- runtime packet: the pre-contour sterile probe returned
  `TOOL_BINARY_NOT_FOUND`, `changed_files=[]`, and no operational authority
- supporting docs: official Qwen Code headless and authentication documentation
  at `https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/` and
  `https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/`
