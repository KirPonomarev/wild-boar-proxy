<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: R63 Workflow Visible Context Boundary

## Status

Accepted for R63.

## Context

B13 previously advanced only an opaque digest between steps while its dispatch
callable received no prior output. That proves ordering but cannot prove that a
later actor saw useful context. Passing an unbounded transcript would create a
separate privacy, prompt-injection, and payload-growth failure.

## Decision

- The runner builds an internal bounded context material value for each
  completed step from already-redacted prior material, the current task, and
  the redacted provider output.
- `fresh` receives no prior visible material; `continue` receives the previous
  completed material; `fork` receives material from the named completed step.
- The production dispatch input carries the visible material plus its source
  and digest. Receipts persist only proof facts and the separately bounded
  output, never a raw context transcript.
- A production result must affirm the exact visible-context digest before a
  context-bearing step can count as delivered.
- The registry-bound dispatcher composes role, verified prior context, and the
  current task into a fixed labeled prompt and sends that exact value through
  the normalized API transport request.
- Live execution is a distinct mode and requires an exact server-owned
  authorization fact. Controlled execution remains useful for deterministic
  code proof but is always labeled non-live.

## Consequences

- Sequential actors receive useful, inspectable-by-digest context rather than
  an inert hash.
- Context size and receipt exposure stay bounded.
- A transport implementation cannot silently ignore prior context and still
  produce a successful workflow receipt.
- Web and other callers can later reuse the same production dispatcher without
  reimplementing identity, ambiguity, or context rules.

## Rejected Alternatives

- Digest-only chaining: preserves integrity metadata but does not deliver
  working context.
- Persisting full transcripts in receipts: unnecessarily expands the sensitive
  evidence surface.
- Letting the caller pre-compose context: permits identity and context-proof
  drift outside the server-owned execution boundary.
- Treating controlled adapter output as live proof: violates the plan's
  evidence separation.
