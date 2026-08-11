<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R59 API Transport Truth Hardening

## Objective

Repair reproduced B07 API adapter truth defects before connecting the adapter
to production workflows. Controlled dispatch must remain credential-free;
provider HTTP errors must never become successful actor output; and any failure
after the request boundary must report an ambiguous, non-retryable delivery
instead of claiming that dispatch was not attempted.

## In Scope

- Separate route admission from live credential admission so deterministic
  controlled dispatch never reads or requires a credential.
- Bind each request to the exact dispatch, transport, provider, model, slot,
  binding, assignment, permission, context, and registered route identities.
- Reject caller-supplied route drift and secret-shaped prompt values before any
  provider invocation.
- Classify non-2xx HTTP responses into the normalized typed error taxonomy.
- Distinguish pre-dispatch failure, observed provider error, successful provider
  response, and ambiguous post-invocation failure with explicit receipt facts.
- Replace raw exception text with bounded static messages and redact provider
  output before it enters a receipt.
- Correct normalized result classification when a response is observed but an
  error code is present.
- Make this repair a unique mandatory GateEvidenceBundleV2 stage supplementing
  the immutable historical B07 receipt.
- Update the normalized transport contract and record its canon digest
  transition.
- Add the adapter and normalization regression suites to the baseline core CI
  selection.

## Out of Scope

- Real provider calls, credential onboarding, Keychain mutation, model
  discovery, or live-evidence closure.
- Sequential workflow, web workflow, CLI, ACP, UI, release, or publication
  changes.
- Main Codex profile/auth/session, protected network surfaces, ports `10808`
  and `12334`, or the user-owned dirty canonical checkout.
- Rewriting or deleting historical evidence receipts or Git history.

## Constraints

- Exact preimage: `origin/main` commit
  `19b014b1a72d61fb6677ffd0bc675070ff8e6413` and canon digest
  `46ac14cb775a40e352ddcdf47e22ca0829520ef71f4220d99982f0110c90fae1`.
- Declared write set:
  `wild_boar_proxy/api_transport_adapter.py`,
  `wild_boar_proxy/transport_normalization.py`,
  `wild_boar_proxy/gate_evidence_bundle_v2.py`,
  `tests/test_api_transport_adapter.py`,
  `tests/test_transport_normalization.py`,
  `tests/test_gate_evidence_bundle_v2.py`, `Makefile`,
  `RUNTIME_CONTRACT.md`, this spec, and this contour's closeout.
- Tests use patched in-process HTTP boundaries only; no external network or
  credential value is admitted.
- Ambiguous delivery has zero retries and never triggers fallback or actor
  substitution.
- Receipts never contain raw provider payloads, raw exception text, secret
  values, or unregistered route overrides.
- The old B07 evidence reference remains immutable. R59 uses a distinct stage
  identifier and becomes an additional required execution-core receipt.

## Assumptions

- Invocation of `request_json(...)` is the conservative boundary after which
  an exception cannot prove that the provider did not receive the request.
- A returned HTTP response proves response observation but does not prove a
  successful actor dispatch unless the status is 2xx and the normalized output
  is non-empty.
- Existing route-registry ownership remains authoritative for endpoint and auth
  configuration.

## Acceptance Criteria

- [x] Controlled dispatch succeeds against an admitted bearer route without a
      credential probe or provider call.
- [x] HTTP 401/403, 404, 408, 429, and 5xx responses return typed errors and can
      never set `live_provider_proven=true`.
- [x] An exception after `request_json(...)` starts returns
      `ambiguous_delivery`, `dispatch_attempted=true`, and
      `retry_permitted=false`.
- [x] Pre-dispatch admission/header/build failures return
      `dispatch_attempted=false` with bounded static messages.
- [x] Exact request/plan/route identity drift and secret-shaped prompt values
      fail before the provider boundary.
- [x] Successful output is non-empty, redacted, digest-bound, and marked
      `LIVE_PROVEN`; controlled output remains `SYNTHETIC_PROVEN`.
- [x] Observed error responses classify as `error`, not `ok`.
- [x] R59 is required by GateEvidenceBundleV2 without duplicating the B07 stage
      or rewriting its receipt.
- [x] Focused, core, collection, closeout-resilience, and hygiene checks pass;
      exact-candidate CI remains a delivery/merge gate.

## Verification

- tests: focused adapter, normalization, and evidence-bundle suites passed 71
  tests and 7 subtests; `make test-core` passed 611 tests and 132 subtests;
  `make test-full` passed 5046 tests and 985 subtests with one known Pillow
  deprecation warning
- build: `make check` compiled repository Python surfaces and collected 5046
  tests; `make test-custom-stability` passed 27 tests and 5 subtests
- manual: six deterministic patched-boundary canaries passed for controlled
  bearer admission, HTTP error truth, ambiguous post-invocation failure, route
  mutation, response redaction, and cross-chunk stream redaction
- live evidence: none; `B07_LIVE` and `B08_LIVE` remain explicitly pending

## Open Questions

- None for this contour.
