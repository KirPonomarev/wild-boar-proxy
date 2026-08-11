<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: One-Shot CLI Uses Immutable Declarations Plus Exact Binary Admissions

## Status

Accepted

## Date

2026-08-11

## Context

The B09 runtime already has useful process-group, environment, home, parser,
and macOS seatbelt machinery, but its production facade is permanently disabled
and its server-owned manifest is empty. Tests inject fake manifests directly,
while production cannot safely admit any real tool. Simply populating the tuple
would be unsafe: an executable found later on a mutable search path could change
version or content without invalidating the code declaration.

This decision is expensive to reverse because Qwen, Kimi, workflow dispatch,
evidence receipts, upgrade invalidation, and account isolation all depend on
the same executable identity and production/test separation.

## Decision

Use two independently required server-owned layers:

1. An immutable code declaration defines the tool/provider identity and every
   permitted execution surface: binary name, version probe, argv schema,
   environment keys, cwd policy, parser, bounds, process-group termination,
   sandbox, auth strategy, session capability, and network policy.
2. An external WBP-owned admission record binds one declaration digest to the
   exact executable realpath, content digest, and observed version. Admissions
   are written atomically under a fixed mode-`0700` root with a real lock and
   mode-`0600` files. They are never selected through environment variables.

Both layers must validate immediately before an operational spawn. Missing or
drifted identity fails closed. Probe is allowed without an admission because it
is the mechanism that observes the candidate, but it still runs under the same
sterile home, environment, output bounds, process group, and deny-default OS
sandbox. Provider inference additionally requires that the provider-specific
adapter and network policy be admitted; B09 declarations alone never grant it.

The production facade remains immutable after construction. Test engines may
still use explicit fake declarations, but test activity cannot mutate the
production facade or its admission source. Captured child output is redacted
before packet serialization, and raw exception text is not a receipt surface.

## Alternatives Considered

1. Keep production permanently disabled and use fake engines indefinitely.
   Rejected: it cannot satisfy B09 or support API/CLI and CLI/CLI workflows.
2. Populate a manifest and trust whatever executable resolves from `PATH`.
   Rejected: binary/version drift could silently change the admitted runtime.
3. Enable production with an environment variable or caller-supplied manifest.
   Rejected: recreates the mutable test-hook/global-grant flaw repaired by R51
   and lets an untrusted caller widen executable and sandbox authority.
4. Vendor provider binaries into the repository.
   Rejected: bloats source history, complicates licensing/upgrades, and mixes
   external binary distribution with product code.

## Consequences

- Positive:
  - Production and test configuration remain structurally separated.
  - Binary and manifest drift have a deterministic pre-spawn invalidation path.
  - Provider stages can reuse one admission truth instead of inventing their
    own executable registries.
  - Missing binaries/login/network stay honest typed prerequisites.
- Negative:
  - A real tool needs an explicit probe/admission after installation or upgrade.
  - Provider-specific contours must define exact argv, parser, and network
    policy before inference can be operational.
- Follow-up work:
  - B10 admits the Qwen invocation/output/home policy.
  - B11 admits the Kimi invocation/output/snapshot policy.
  - B17 exercises binary revision drift, auth expiry, and upgrade invalidation.

## Evidence

- spec: `audit_results/R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION_SPEC_2026-08-11.md`
- tests: R60 focused admission, drift, redaction, and production/test isolation
  suites
- runtime packet: no live provider packet; current binaries are absent
- supporting docs: approved master plan sections 7, 14, 19, 20/B09, and the
  official Qwen/Kimi CLI path and headless-mode documentation reviewed on
  2026-08-11
