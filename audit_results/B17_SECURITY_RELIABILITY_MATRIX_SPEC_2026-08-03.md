<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B17 Security / Reliability / Advanced-Capability / Upgrade Matrix

## Objective

Build the repository-native security and reliability matrix: run
deterministic local probes for fuzzing, malformed/large streams,
cancellation, corruption/recovery, binary and revision drift, auth expiry,
provider failures, injection/redaction, lease contention, app restart,
Codex upgrade invalidation guard, admitted advanced capabilities, and
protected-surface guards. Each matrix entry carries honest evidence;
guarded surfaces (owner safety override) are reported as guarded, never
simulated.

## In Scope

- `wild_boar_proxy/security_reliability_matrix.py` (new):
  - matrix checks (each a deterministic local probe):
    - fuzzing: parser fuzz over malformed/empty/huge inputs
    - malformed/large streams: stream accumulator with truncation and
      oversized deltas
    - cancellation: one-shot process-group cancellation (fake adapter)
    - corruption/recovery: ledger recovery with malformed entries
    - binary/revision drift: tool digest drift + revision mismatch
    - auth expiry: repo-lease TTL expiry probe
    - provider failures: transport error taxonomy (401/403/404/429/5xx)
    - injection/redaction: packet redaction + injection containment
    - lease contention: two acquirers, one lease
    - app restart: state startup/recovery probe
    - Codex upgrade invalidation: protected-surface guard in force
      (Codex state is never read — owner safety override); reported as
      guarded
    - admitted advanced capabilities: qwen thinking, kimi immutable
      snapshot, glm API_ONLY admission
    - protected-surface guards: main-Codex air-gap facts, protected ports
  - `run_security_reliability_matrix()`: aggregate packet with per-check
    evidence; strict command packet; honest statuses
- tests: `tests/test_security_reliability_matrix.py`
- B17 spec + closeout in `audit_results/`

## Out of Scope

- live credential probes (live phases)
- Codex surface reads (forbidden by the owner safety override; the guard
  itself is verified instead)
- any canon change (no command/state schema touch)

## Constraints

- every check is a real deterministic probe or an honest guarded result;
  no greenwashing
- the main Codex surface is never touched; the guard is the evidence
- secret values never appear in matrix packets
- matrix packets are strict command packets

## Assumptions

- existing contour machinery (stream accumulator, one-shot runtime,
  ledger, repo lease, transport taxonomy, redaction, qwen/kimi/glm
  slices) is the probe surface

## Acceptance Criteria

- [ ] every matrix category has a check with honest evidence
- [ ] guarded categories report guarded with the guard reason
- [ ] aggregate packet is strict and contains no secrets
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_security_reliability_matrix.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: `run_security_reliability_matrix()` recorded in the closeout
- live evidence: none (deterministic probes only)

## Open Questions

- None blocking.
